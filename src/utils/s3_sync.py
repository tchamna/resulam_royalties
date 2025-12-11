"""
S3 Data Synchronization Module
Downloads data files from S3 on application startup to ensure latest data is always used.
"""
import os
import boto3
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


def download_s3_files(bucket: str, files: List[Tuple[str, str]], region: str = 'us-east-1') -> bool:
    """
    Download files from S3 bucket to local paths.
    
    Args:
        bucket: S3 bucket name
        files: List of tuples (s3_key, local_path)
        region: AWS region
    
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
                print(f"   Downloading {s3_key}...")
                s3.download_file(bucket, s3_key, str(local_path))
                print(f"   ✓ Saved to {local_path}")
                success_count += 1
            except Exception as e:
                print(f"   ✗ Failed to download {s3_key}: {e}")
        
        return success_count == len(files)
    except Exception as e:
        print(f"✗ S3 client error: {e}")
        return False


def sync_data_on_startup():
    """
    Sync data files from S3 on application startup.
    Called automatically when USE_S3_DATA=true.
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
    
    return success
