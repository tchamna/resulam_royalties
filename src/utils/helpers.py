"""
Utility functions for file operations and data export
"""
import pandas as pd
from pathlib import Path
from typing import Dict

from ..config import DASHBOARD_CONFIG, LAST_YEAR


def export_processed_data(data: Dict[str, pd.DataFrame], output_dir: Path = None):
    """
    Export processed data to CSV files
    
    Args:
        data: Dictionary containing processed dataframes
        output_dir: Directory to save files (defaults to project root)
    """
    if output_dir is None:
        output_dir = Path.cwd()
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export main royalties data
    royalties_file = output_dir / f"royalties_resulambooks_from_2015_{LAST_YEAR}_history_df.csv"
    data['royalties_history'].to_csv(royalties_file, encoding="utf-8-sig", index=False)
    print(f"✅ Saved: {royalties_file}")
    
    # Export exploded authors data
    exploded_file = output_dir / f"royalties_exploded_{LAST_YEAR}.csv"
    data['royalties_exploded'].to_csv(exploded_file, encoding="utf-8-sig", index=False)
    print(f"✅ Saved: {exploded_file}")
    
    # Export author summary
    author_summary = data['royalties_exploded'].groupby('Authors_Exploded').agg({
        'Units Sold': 'sum',
        'Royalty per Author (USD)': 'sum'
    }).reset_index()
    
    # Apply adjustments for authors with < $100
    adjusted_amount = DASHBOARD_CONFIG['adjusted_amount']
    author_summary['Adjusted Royalty (USD)'] = author_summary['Royalty per Author (USD)'].apply(
        lambda x: round(x + adjusted_amount, 2) if x < 100 else round(x, 2)
    )
    
    # Convert to XAF
    conversion_rate = DASHBOARD_CONFIG['conversion_rate_xaf']
    author_summary['Royalty (FCFA)'] = author_summary['Adjusted Royalty (USD)'] * conversion_rate
    
    # Sort and save
    author_summary = author_summary.sort_values(by='Adjusted Royalty (USD)', ascending=False)
    author_summary = author_summary.rename(columns={'Authors_Exploded': 'Author'})
    
    author_file = output_dir / f"royalties_per_author_{LAST_YEAR}.csv"
    author_summary.to_csv(author_file, encoding="utf-8-sig", index=False)
    print(f"✅ Saved: {author_file}")
    
    return {
        'royalties': royalties_file,
        'exploded': exploded_file,
        'authors': author_file
    }


def validate_data_files(files: list) -> bool:
    """
    Validate that required data files exist
    
    Args:
        files: List of file paths to check
        
    Returns:
        True if all files exist, False otherwise
    """
    missing_files = []
    
    for file in files:
        file_path = Path(file)
        if not file_path.exists():
            missing_files.append(str(file_path))
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    print("✅ All required data files found")
    return True
