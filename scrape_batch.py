import pandas as pd
import time
import os
from scrape_single_property import extract_property_data, calculate_roof_age

def get_last_processed_row(progress_file: str = "progress.txt"):
    """
    Get information about the last processed row from the progress file
    """
    if not os.path.exists(progress_file):
        return {"status": "not_started", "last_row": None}
    
    try:
        with open(progress_file, 'r') as f:
            content = f.read().strip()
            if content.startswith("COMPLETED_"):
                end_row = int(content.replace("COMPLETED_", ""))
                return {"status": "completed", "last_row": end_row}
            else:
                last_row = int(content)
                return {"status": "in_progress", "last_row": last_row}
    except (ValueError, FileNotFoundError):
        return {"status": "error", "last_row": None}

def run_batch(csv_path: str, start_row: int = 0, end_row: int = None, out_path: str = "final_results_Seminole.csv", progress_file: str = "progress.txt"):
    # Load the Seminole property URLs CSV
    df = pd.read_csv(csv_path)
    
    # Extract STRAP from PROPERTY_URL (everything after the last '=')
    df['STRAP'] = df['PROPERTY_URL'].str.extract(r's=([^&]+)')
    
    # Set end_row to total length if not specified
    if end_row is None:
        end_row = len(df) - 1
    
    # Validate range
    if start_row < 0 or end_row >= len(df) or start_row > end_row:
        raise ValueError(f"Invalid range: start_row={start_row}, end_row={end_row}, total_rows={len(df)}")
    
    print(f"Processing rows {start_row} to {end_row} ({end_row - start_row + 1} properties)")
    print(f"Total properties in CSV: {len(df)}")

    # If CSV doesn't exist, write header first
    if not os.path.exists(out_path):
        pd.DataFrame(columns=[
            "STRAP", "First Name", "Last Name", "Address 1", "City", "State", "Zip", 
            "Property Use", "Roof Cover", "Living SF", "Roofing Permit Age", 
            "Shingle over 15 years old (Y/N)", "Tile over 20 years old (Y/N)", 
            "Property URL", "Pass"
        ]).to_csv(out_path, index=False)

    # Process the specified range
    for i in range(start_row, end_row + 1):
        row = df.iloc[i]
        strap = row['STRAP']
        
        # Save current progress
        with open(progress_file, 'w') as f:
            f.write(str(i))
            
        print(f"\n[Row {i}/{end_row}] Processing STRAP: {strap}")

        try:
            data = extract_property_data(strap)

            # ✅ Only process 0110 Single Family units
            if not data.get("use_code") or "0110" not in data["use_code"]:
                print("❌ Skipped – Not a single-family unit (0110).")
                continue

            analysis = calculate_roof_age(data)
            
            # Determine tile over 20 years logic
            roof_type = (data.get("roof_cover") or "").lower()
            tile_over_20 = "N"
            if "tile" in roof_type or "concrete" in roof_type:
                tile_over_20 = "Y" if analysis.get("roof_age", 0) >= 20 else "N"

            result = {
                "STRAP": strap,
                "First Name": data.get("first_name"),
                "Last Name": data.get("last_name"),
                "Address 1": data.get("address_1"),
                "City": data.get("city"),
                "State": data.get("state"),
                "Zip": data.get("zip"),
                "Property Use": data.get("use_code"),
                "Roof Cover": data.get("roof_cover"),
                "Living SF": data.get("living_sf"),
                "Roofing Permit Age": analysis.get("roof_age"),
                "Shingle over 15 years old (Y/N)": "Y" if analysis.get("pass") and "shingle" in roof_type else "N",
                "Tile over 20 years old (Y/N)": tile_over_20,
                "Property URL": f"https://www.pcpao.gov/property-details?s={strap}",
                "Pass": "Y" if analysis.get("pass") else "N"
            }

            # ✅ Append to CSV immediately
            pd.DataFrame([result]).to_csv(out_path, mode='a', index=False, header=False)
            print(f"✅ Single-family unit processed and saved!")

        except Exception as e:
            print(f"❌ Failed on {strap}: {e}")

        time.sleep(10)  # Respect crawl-delay

    # Mark completion
    with open(progress_file, 'w') as f:
        f.write(f"COMPLETED_{end_row}")
        
    print(f"\n✅ Done processing rows {start_row} to {end_row}. Results saved to {out_path}")

def get_last_processed_row(progress_file: str = "progress.txt"):
    """Get the last processed row from the progress file"""
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            content = f.read().strip()
            if content.startswith("COMPLETED_"):
                return f"Completed up to row {content.split('_')[1]}"
            else:
                return f"Last processed row: {content}"
    return "No progress file found"

if __name__ == "__main__":
    # Example usage: process rows 0 to 99 (first 100 rows)
    run_batch("seminole_property_urls.csv", start_row=87, end_row=14998)
