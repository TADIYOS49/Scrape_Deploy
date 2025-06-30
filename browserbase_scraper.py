#!/usr/bin/env python3
"""
Browserbase-optimized scraper for Seminole property data
To run locally: 
    export BROWSERBASE_API_KEY=your_key_here
    python browserbase_scraper.py

For deployment to Browserbase platform, this script will be executed in their cloud environment.
"""

import os
import sys
from scrape_batch import run_batch, get_last_processed_row

def main(csv_path="seminole_property_urls.csv", start_row=None, end_row=None, 
         output_file="final_results_Seminole.csv", chunk_size=100, progress_file="progress.txt"):
    """
    Main scraper function with configurable parameters
    
    Args:
        csv_path (str): Path to the CSV file with property URLs
        start_row (int): Starting row number to process (default: 0, first row)
        end_row (int): Ending row number to process (default: last row of CSV)
        output_file (str): Name of the output CSV file
        chunk_size (int): Number of properties to process per chunk
        progress_file (str): Name of the progress tracking file
    """
    # Check for API key
    api_key = os.getenv('BROWSERBASE_API_KEY')
    if not api_key:
        print("❌ Error: BROWSERBASE_API_KEY environment variable not set")
        print("Please set it with: export BROWSERBASE_API_KEY=your_key_here")
        sys.exit(1)
    
    print("✅ Browserbase API key found")
    
    # Load CSV to determine defaults if not provided
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        total_rows = len(df)
        
        # Set defaults based on CSV file
        if start_row is None:
            start_row = 0  # First row
        if end_row is None:
            end_row = total_rows - 1  # Last row (0-indexed)
            
        print(f"📁 CSV file '{csv_path}' loaded: {total_rows} total rows")
        print(f"📊 Processing range: {start_row} to {end_row} ({end_row - start_row + 1} rows)")
        
    except FileNotFoundError:
        print(f"❌ Error: CSV file '{csv_path}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        sys.exit(1)
    
    # Check what was last processed
    progress_info = get_last_processed_row(progress_file)
    print(f"📊 Progress info: {progress_info}")
    
    print(f"🚀 Starting batch processing from row {start_row} to {end_row}")
    print(f"📁 Input file: {csv_path}")
    print(f"💾 Output file: {output_file}")
    print(f"🔢 Chunk size: {chunk_size}")
    print(f"📋 Progress file: {progress_file}")
    
    # Process in chunks to avoid timeouts
    current_start = start_row
    while current_start <= end_row:
        current_end = min(current_start + chunk_size - 1, end_row)
        
        print(f"\n📦 Processing chunk: rows {current_start} to {current_end}")
        
        try:
            run_batch(
                csv_path=csv_path,
                start_row=current_start,
                end_row=current_end,
                out_path=output_file,
                progress_file=progress_file
            )
            print(f"✅ Completed chunk: rows {current_start} to {current_end}")
            
        except Exception as e:
            print(f"❌ Error processing chunk {current_start}-{current_end}: {e}")
            # Continue with next chunk rather than failing completely
            
        current_start = current_end + 1
    
    print(f"\n🎉 Batch processing complete! Results saved to {output_file}")

if __name__ == "__main__":
    main() 