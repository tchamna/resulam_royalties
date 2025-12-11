#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload local data files to S3 bucket for EC2 deployment
This script uploads the required data files to S3 and configures the GitHub secret.
"""

import boto3
import os
import sys
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError

# Load configuration from environment or .env
def load_env_file(env_file='.env'):
    """Load environment variables from .env file"""
    if not os.path.exists(env_file):
        return
    
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip()
    except Exception as e:
        print(f"Warning: Could not read {env_file}: {e}")

load_env_file('.env')

# Configuration
S3_BUCKET = os.getenv('S3_BUCKET')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

# Local data files (update paths as needed)
LOCAL_DATA_DIR = Path(r"G:\My Drive\Mbú'ŋwɑ̀'nì\RoyaltiesResulam")

DATA_FILES = [
    "Resulam_books_database_Amazon_base_de_donnee_livres.csv",
    "KDP_OrdersResulamBookSales2015_2025RoyaltiesReportsHistory.xlsx"
]

def upload_to_s3():
    """Upload data files to S3 bucket"""
    print("\n" + "="*70)
    print("📤 UPLOAD DATA FILES TO S3")
    print("="*70)
    
    # Validate configuration
    if not S3_BUCKET:
        print("❌ S3_BUCKET not set. Set it with: export S3_BUCKET=your-bucket-name")
        return False
    
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        print("❌ AWS credentials not set.")
        print("   Set them with:")
        print("   export AWS_ACCESS_KEY_ID=your-key-id")
        print("   export AWS_SECRET_ACCESS_KEY=your-secret-key")
        return False
    
    print(f"\n📦 S3 Bucket: {S3_BUCKET}")
    print(f"🌍 AWS Region: {AWS_REGION}")
    print(f"📁 Local Data Directory: {LOCAL_DATA_DIR}")
    print(f"\n📋 Files to upload:")
    
    # Check if files exist
    missing_files = []
    for file in DATA_FILES:
        file_path = LOCAL_DATA_DIR / file
        if file_path.exists():
            size = file_path.stat().st_size / (1024 * 1024)  # MB
            print(f"   ✓ {file} ({size:.2f} MB)")
        else:
            print(f"   ❌ {file} - NOT FOUND")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n❌ Missing files: {', '.join(missing_files)}")
        print("\n💡 Update LOCAL_DATA_DIR in this script to point to your data files.")
        return False
    
    # Create S3 client
    try:
        s3_client = boto3.client(
            's3',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        
        # Test connection by checking if bucket exists
        try:
            s3_client.head_bucket(Bucket=S3_BUCKET)
            print(f"\n✅ S3 bucket '{S3_BUCKET}' accessible")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                print(f"\n❌ S3 bucket '{S3_BUCKET}' does not exist.")
                print(f"   Create it with: aws s3 mb s3://{S3_BUCKET} --region {AWS_REGION}")
                return False
            elif error_code == 403:
                print(f"\n❌ Access denied to bucket '{S3_BUCKET}'.")
                print(f"   Check your AWS credentials and bucket permissions.")
                return False
            else:
                raise
        
    except NoCredentialsError:
        print("\n❌ AWS credentials not found or invalid.")
        return False
    except Exception as e:
        print(f"\n❌ Error connecting to S3: {e}")
        return False
    
    # Upload files
    print(f"\n📤 Uploading files...")
    success_count = 0
    
    for file in DATA_FILES:
        file_path = LOCAL_DATA_DIR / file
        try:
            print(f"\n   Uploading {file}...", end=' ')
            s3_client.upload_file(
                str(file_path),
                S3_BUCKET,
                file,
                ExtraArgs={'ContentType': 'application/octet-stream'}
            )
            print("✅")
            success_count += 1
        except Exception as e:
            print(f"❌\n   Error: {e}")
    
    if success_count == len(DATA_FILES):
        print(f"\n✅ All {success_count} files uploaded successfully!")
        
        # Generate S3_DATA_FILES value
        s3_files_value = "|".join(DATA_FILES)
        
        print("\n" + "="*70)
        print("🔐 CONFIGURE GITHUB SECRET")
        print("="*70)
        print(f"\nAdd the following GitHub repository secret:")
        print(f"\n   Secret Name:  S3_DATA_FILES")
        print(f"   Secret Value: {s3_files_value}")
        print(f"\n📝 Using GitHub CLI:")
        print(f"   gh secret set S3_DATA_FILES -b \"{s3_files_value}\"")
        print(f"\n📝 Or manually at:")
        print(f"   https://github.com/tchamna/resulam_royalties/settings/secrets/actions")
        
        return True
    else:
        print(f"\n⚠️  Only {success_count}/{len(DATA_FILES)} files uploaded.")
        return False

def set_github_secret():
    """Set S3_DATA_FILES GitHub secret"""
    try:
        import subprocess
        
        s3_files_value = "|".join(DATA_FILES)
        
        # Check if gh CLI is available
        result = subprocess.run(['gh', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("\n⚠️  GitHub CLI (gh) not installed.")
            print("   Install from: https://cli.github.com")
            return False
        
        print("\n🔐 Setting GitHub secret S3_DATA_FILES...")
        
        # Set the secret
        process = subprocess.Popen(
            ['gh', 'secret', 'set', 'S3_DATA_FILES', '--repo', 'tchamna/resulam_royalties'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=s3_files_value, timeout=10)
        
        if process.returncode == 0:
            print("✅ GitHub secret S3_DATA_FILES set successfully!")
            return True
        else:
            print(f"❌ Failed to set secret: {stderr}")
            return False
            
    except Exception as e:
        print(f"\n⚠️  Could not set GitHub secret automatically: {e}")
        return False

if __name__ == '__main__':
    try:
        # Upload files to S3
        upload_success = upload_to_s3()
        
        if not upload_success:
            sys.exit(1)
        
        # Try to set GitHub secret
        print("\n" + "="*70)
        if '--set-secret' in sys.argv or input("\nSet GitHub secret now? (y/n): ").lower() == 'y':
            set_github_secret()
        
        print("\n✅ Setup complete! Your next deployment will download data from S3.")
        print("\n" + "="*70)
        
    except KeyboardInterrupt:
        print("\n\n❌ Upload cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
