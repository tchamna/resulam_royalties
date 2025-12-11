"""
S3 Data Synchronization Module
Downloads data files from S3 on application startup to ensure latest data is always used.
Includes periodic background sync to automatically detect and download S3 updates.
"""
import os
import boto3
from pathlib import Path
from typing import List, Tuple
import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# Global flag to track if background sync is running
_sync_thread = None
_stop_sync = False


def download_s3_files(bucket: str, files: List[Tuple[str, str]], region: str = 'us-east-1', quiet: bool = False) -> bool:
    """
    Download files from S3 bucket to local paths.
    
    Args:
        bucket: S3 bucket name
        files: List of tuples (s3_key, local_path)
        region: AWS region
        quiet: If True, suppress download progress messages
    
    Returns:
        True if all files downloaded successfully, False otherwise
    """
    try:
        s3 = boto3.client('s3', region_name=region)
        success_count = 0
        
        for s3_key, local_path in files:
            try:
                # Ensure directory exists
                Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                
                # Download file
                if not quiet:
                    print(f"   Downloading {s3_key}...")
                s3.download_file(bucket, s3_key, str(local_path))
                if not quiet:
                    print(f"   ✓ Saved to {local_path}")
                success_count += 1
            except Exception as e:
                if not quiet:
                    print(f"   ✗ Failed to download {s3_key}: {e}")
        
        return success_count == len(files)
    except Exception as e:
        if not quiet:
            print(f"✗ S3 client error: {e}")
        return False


def check_s3_file_modified(bucket: str, s3_key: str, local_path: str, region: str = 'us-east-1') -> bool:
    """
    Check if S3 file is newer than local file.
    
    Args:
        bucket: S3 bucket name
        s3_key: S3 object key
        local_path: Local file path
        region: AWS region
    
    Returns:
        True if S3 file is newer or local file doesn't exist
    """
    try:
        if not os.path.exists(local_path):
            return True
        
        s3 = boto3.client('s3', region_name=region)
        response = s3.head_object(Bucket=bucket, Key=s3_key)
        s3_last_modified = response['LastModified']
        
        local_modified = datetime.fromtimestamp(os.path.getmtime(local_path))
        # Make local_modified timezone-aware to match S3
        local_modified = local_modified.replace(tzinfo=s3_last_modified.tzinfo)
        
        return s3_last_modified > local_modified
    except Exception as e:
        logger.warning(f"Error checking S3 file modification time: {e}")
        return False


def background_sync_worker(bucket: str, files: List[Tuple[str, str]], region: str, interval: int):
    """
    Background worker that periodically checks for S3 updates.
    
    Args:
        bucket: S3 bucket name
        files: List of tuples (s3_key, local_path)
        region: AWS region
        interval: Check interval in seconds
    """
    global _stop_sync
    
    while not _stop_sync:
        try:
            # Check each file for updates
            files_to_update = []
            for s3_key, local_path in files:
                if check_s3_file_modified(bucket, s3_key, local_path, region):
                    files_to_update.append((s3_key, local_path))
            
            # Download updated files
            if files_to_update:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n🔄 [{timestamp}] Detected {len(files_to_update)} updated file(s) in S3, syncing...")
                
                if download_s3_files(bucket, files_to_update, region, quiet=True):
                    print(f"✅ [{timestamp}] S3 sync completed - Restarting container to reload data...")
                    # Exit the process to trigger container restart (Docker --restart unless-stopped)
                    import sys
                    sys.exit(0)
                else:
                    print(f"⚠️  [{timestamp}] Some files failed to sync")
        
        except Exception as e:
            logger.error(f"Background sync error: {e}")
        
        # Sleep for the interval
        for _ in range(interval):
            if _stop_sync:
                break
            time.sleep(1)


def start_background_sync(bucket: str, files: List[Tuple[str, str]], region: str = 'us-east-1', interval: int = 300):
    """
    Start background thread to periodically check for S3 updates.
    
    Args:
        bucket: S3 bucket name
        files: List of tuples (s3_key, local_path)
        region: AWS region
        interval: Check interval in seconds (default: 300 = 5 minutes)
    """
    global _sync_thread, _stop_sync
    
    if _sync_thread and _sync_thread.is_alive():
        print("Background S3 sync already running")
        return
    
    _stop_sync = False
    _sync_thread = threading.Thread(
        target=background_sync_worker,
        args=(bucket, files, region, interval),
        daemon=True,
        name="S3-Background-Sync"
    )
    _sync_thread.start()
    print(f"🔄 Background S3 sync started (checking every {interval} seconds)")


def stop_background_sync():
    """Stop the background sync thread."""
    global _stop_sync, _sync_thread
    
    _stop_sync = True
    if _sync_thread:
        _sync_thread.join(timeout=5)
        print("Background S3 sync stopped")


def sync_data_on_startup():
    """
    Sync data files from S3 on application startup.
    Called automatically when USE_S3_DATA=true.
    Also starts background sync if AUTO_SYNC_INTERVAL is set.
    """
    use_s3 = os.getenv('USE_S3_DATA', 'false').lower() == 'true'
    
    if not use_s3:
        print("S3 sync skipped (USE_S3_DATA not enabled)")
        return True
    
    bucket = os.getenv('S3_BUCKET')
    region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    
    if not bucket:
        print("⚠️  S3_BUCKET not set, skipping S3 sync")
        return False
    
    # Define files to download (S3 key -> local path)
    # Use /app/data for Docker container, otherwise use project data dir
    if os.path.exists('/app'):
        data_dir = Path('/app/data')
    else:
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "data"
    
    files_to_download = [
        ('KDP_OrdersResulamBookSales2015_2025RoyaltiesReportsHistory.xlsx', 
         str(data_dir / 'KDP_OrdersResulamBookSales2015_2025RoyaltiesReportsHistory.xlsx')),
        ('Resulam_books_database_Amazon_base_de_donnee_livres.csv',
         str(data_dir / 'Resulam_books_database_Amazon_base_de_donnee_livres.csv')),
    ]
    
    print(f"📡 Syncing {len(files_to_download)} files from s3://{bucket}")
    success = download_s3_files(bucket, files_to_download, region)
    
    if success:
        print("✅ All data files synced from S3")
    else:
        print("⚠️  Some S3 files failed to download")
    
    # Start background sync if enabled
    auto_sync_interval = os.getenv('AUTO_SYNC_INTERVAL')
    if auto_sync_interval:
        try:
            interval = int(auto_sync_interval)
            if interval > 0:
                start_background_sync(bucket, files_to_download, region, interval)
        except ValueError:
            logger.warning(f"Invalid AUTO_SYNC_INTERVAL value: {auto_sync_interval}")
    
    return success
