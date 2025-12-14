"""
Image Compression Script for Resulam Book Covers
Compresses images without losing quality using optimization techniques.
Uses parallel processing for faster compression.
"""

import os
from pathlib import Path
from PIL import Image
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configuration
SOURCE_DIR = r"G:\My Drive\Mbú'ŋwɑ̀'nì\Album_ResulamBooks_Livres_Resulam_2015_2023_QRCodes\ResulamBookCoversQRCode"
OUTPUT_DIR = r"G:\My Drive\Mbú'ŋwɑ̀'nì\Album_ResulamBooks_Livres_Resulam_2015_2023_QRCodes\ResulamBookCoversQRCode_Compressed"

# Compression settings
JPEG_QUALITY = 85  # 85 is a good balance between quality and size
PNG_COMPRESSION = 9  # Max compression for PNG (0-9)
MAX_DIMENSION = 2000  # Max width or height (set to None to keep original size)
MAX_WORKERS = 8  # Number of parallel threads

# Thread-safe counter
progress_lock = threading.Lock()
progress_counter = {'count': 0, 'total': 0}


def get_file_size_mb(filepath):
    """Get file size in MB"""
    return os.path.getsize(filepath) / (1024 * 1024)


def compress_image(input_path, output_path):
    """
    Compress an image while maintaining quality.
    Returns tuple: (success, original_size_mb, new_size_mb, filename)
    """
    filename = Path(input_path).name
    try:
        original_size = get_file_size_mb(input_path)
        
        # Open the image
        with Image.open(input_path) as img:
            # Get original format
            original_format = img.format
            
            # Convert RGBA to RGB for JPEG (JPEG doesn't support transparency)
            if img.mode == 'RGBA' and original_format == 'JPEG':
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode == 'RGBA' and input_path.lower().endswith(('.jpg', '.jpeg')):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            
            # Optionally resize if too large
            if MAX_DIMENSION:
                width, height = img.size
                if width > MAX_DIMENSION or height > MAX_DIMENSION:
                    ratio = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
                    new_size = (int(width * ratio), int(height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Determine output format and save with optimization
            ext = Path(input_path).suffix.lower()
            
            if ext in ['.jpg', '.jpeg']:
                # For JPEG: use quality setting and optimize
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(output_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)
                
            elif ext == '.png':
                # For PNG: use maximum compression
                img.save(output_path, 'PNG', optimize=True, compress_level=PNG_COMPRESSION)
                
            elif ext == '.webp':
                # For WebP: use quality setting
                img.save(output_path, 'WEBP', quality=JPEG_QUALITY, optimize=True)
                
            elif ext in ['.bmp', '.tiff', '.tif']:
                # Convert to PNG for better compression
                output_path = str(Path(output_path).with_suffix('.png'))
                img.save(output_path, 'PNG', optimize=True, compress_level=PNG_COMPRESSION)
                
            else:
                # For other formats, try to save with optimization
                img.save(output_path, optimize=True)
        
        new_size = get_file_size_mb(output_path)
        
        # Update progress
        with progress_lock:
            progress_counter['count'] += 1
            current = progress_counter['count']
            total = progress_counter['total']
        
        reduction = ((original_size - new_size) / original_size * 100) if original_size > 0 else 0
        print(f"  [{current}/{total}] ✅ {filename}: {original_size:.2f} MB → {new_size:.2f} MB ({reduction:.1f}% reduction)")
        
        return True, original_size, new_size, output_path, filename
        
    except Exception as e:
        with progress_lock:
            progress_counter['count'] += 1
            current = progress_counter['count']
            total = progress_counter['total']
        print(f"  [{current}/{total}] ❌ {filename}: Error - {str(e)}")
        return False, 0, 0, output_path, filename


def main():
    print("=" * 70)
    print("📚 RESULAM BOOK COVERS - IMAGE COMPRESSION SCRIPT")
    print("=" * 70)
    print()
    
    # Check source directory
    source_path = Path(SOURCE_DIR)
    if not source_path.exists():
        print(f"❌ Source directory not found: {SOURCE_DIR}")
        return
    
    print(f"📂 Source: {SOURCE_DIR}")
    print(f"📂 Output: {OUTPUT_DIR}")
    print()
    
    # Create output directory
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.gif'}
    image_files = []
    
    for file in source_path.iterdir():
        if file.is_file() and file.suffix.lower() in image_extensions:
            image_files.append(file)
    
    if not image_files:
        print("❌ No image files found in source directory")
        return
    
    print(f"🖼️  Found {len(image_files)} images to compress")
    print(f"⚡ Using {MAX_WORKERS} parallel threads")
    print("-" * 70)
    
    # Set up progress tracking
    progress_counter['count'] = 0
    progress_counter['total'] = len(image_files)
    
    # Prepare task list
    tasks = []
    for input_file in image_files:
        output_file = output_path / input_file.name
        tasks.append((str(input_file), str(output_file)))
    
    # Process images in parallel
    total_original_size = 0
    total_new_size = 0
    success_count = 0
    
    print("\n🚀 Starting parallel compression...\n")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        futures = {
            executor.submit(compress_image, input_path, output_path): (input_path, output_path)
            for input_path, output_path in tasks
        }
        
        # Collect results
        for future in as_completed(futures):
            success, original_size, new_size, final_output, filename = future.result()
            
            if success:
                success_count += 1
                total_original_size += original_size
                total_new_size += new_size
    
    # Summary
    print()
    print("=" * 70)
    print("📊 COMPRESSION SUMMARY")
    print("=" * 70)
    print(f"  Total images processed: {success_count}/{len(image_files)}")
    print(f"  Original total size:    {total_original_size:.2f} MB")
    print(f"  Compressed total size:  {total_new_size:.2f} MB")
    
    if total_original_size > 0:
        total_reduction = ((total_original_size - total_new_size) / total_original_size * 100)
        saved = total_original_size - total_new_size
        print(f"  Space saved:            {saved:.2f} MB ({total_reduction:.1f}% reduction)")
    
    print(f"\n📂 Compressed images saved to:\n   {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
