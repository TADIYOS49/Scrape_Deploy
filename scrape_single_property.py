from playwright.sync_api import sync_playwright
from browserbase import Browserbase
import time
import os
import re
from datetime import datetime

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system environment variables


def extract_property_data(parcel_id: str):
    # Initialize Browserbase client
    bb = Browserbase(api_key=os.environ.get("BROWSERBASE_API_KEY"))
    
    with sync_playwright() as playwright:
        # Create a session on Browserbase
        session = bb.sessions.create(project_id=os.environ.get("BROWSERBASE_PROJECT_ID"))
        
        # Connect to the remote session
        chromium = playwright.chromium
        browser = chromium.connect_over_cdp(session.connect_url)
        context = browser.contexts[0]
        page = context.pages[0]
        
        # Set longer timeout for slow network
        page.set_default_timeout(180000)  # 3 minutes
        
        url = f"https://www.pcpao.gov/property-details?s={parcel_id}"
        print(f"Loading: {url}")
        page.goto(url)
        
        # Try different wait strategies with error handling
        try:
            page.wait_for_load_state('domcontentloaded', timeout=15000)
            time.sleep(3)  # Let JS render
            print("Page loaded successfully")
        except Exception as e:
            print(f"Wait strategy failed: {e}")
            print("Continuing anyway...")
            time.sleep(5)  # Give it some time anyway

        # Extract basic info using the existing working pattern
        data = page.evaluate(r'''() => {
            const text = (label) => {
                const td = Array.from(document.querySelectorAll('td'))
                    .find(el => el.textContent.trim().includes(label));
                return td ? td.nextElementSibling?.textContent.trim() : null;
            };
            
            // Get living SF from id="tls" directly 
            const livingSfElement = document.getElementById('tls');
            let livingSf = livingSfElement ? livingSfElement.textContent.trim() : null;
            
            // If that doesn't work, try the old method as fallback
            if (!livingSf) {
                const colLivingElement = document.querySelector('.col-total-living');
                if (colLivingElement) {
                    const h2Element = colLivingElement.querySelector('h2');
                    livingSf = h2Element ? h2Element.textContent.trim() : null;
                }
            }
            
            // Get page text for other extractions
            const pageText = document.body.textContent || '';
            
            // Extract data using specific IDs provided by user
            
            // Owner Name: id="owner_details" - Extract raw HTML to preserve <br> tags
            const ownerDetailsDiv = document.getElementById('owner_details');
            let rawOwnerName = null;
            if (ownerDetailsDiv) {
                const ownerHTML = ownerDetailsDiv.innerHTML || '';
                // Keep <br> tags but clean up other HTML
                rawOwnerName = ownerHTML
                    .replace(/<(?!br\s*\/?)[^>]*>/gi, '') // Remove all HTML except <br> tags
                    .replace(/\bMore\b/g, '')  // Remove "More" text
                    .trim();
            }
            
            // Address: id="site_address" - Extract raw HTML to preserve <br> tags
            const siteAddressDiv = document.getElementById('site_address');
            let rawPropertyAddress = null;
            if (siteAddressDiv) {
                const addressHTML = siteAddressDiv.innerHTML || '';
                // Keep <br> tags but clean up other HTML
                rawPropertyAddress = addressHTML
                    .replace(/<(?!br\s*\/?)[^>]*>/gi, '') // Remove all HTML except <br> tags
                    .trim()
                    // Fix missing space before SEMINOLE (e.g., "504SEMINOLE" -> "504 SEMINOLE", "AVESEMINOLE" -> "AVE SEMINOLE")
                    .replace(/([A-Z0-9])SEMINOLE/g, '$1 SEMINOLE');
            }
            
            // Use Code: id="property_use"
            const propertyUseDiv = document.getElementById('property_use');
            let useCode = null;
            if (propertyUseDiv) {
                const useText = propertyUseDiv.textContent || '';
                useCode = useText.trim().replace(/\s+/g, ' ');
            }
            
            // Year Built: id="Yrb"
            const yrbDiv = document.getElementById('Yrb');
            let yearBuilt = null;
            if (yrbDiv) {
                const yearText = yrbDiv.textContent || '';
                yearBuilt = yearText.trim().replace(/\s+/g, ' ');
            }
            
            return {
                raw_owner: rawOwnerName,
                address: rawPropertyAddress,
                use_code: useCode,
                roof_cover: text("Roof Cover") || (() => {
                    // More robust roof cover extraction
                    const rows = Array.from(document.querySelectorAll('tr'));
                    for (let row of rows) {
                        const firstTd = row.querySelector('td');
                        if (firstTd && firstTd.textContent.includes('Roof Cover:')) {
                            const nextTd = firstTd.nextElementSibling;
                            return nextTd ? nextTd.textContent.trim() : null;
                        }
                    }
                    return null;
                })(),
                living_sf: livingSf,             // Keep old version as requested
                year_built: yearBuilt
            };
        }''')
        
        # Process the raw owner data with Python logic
        parsed_data = parse_owner_and_address_data(data)
        
        print(f"Extracted data: {parsed_data}")

        # Extract permits
        permits = page.evaluate('''() => {
            const permitTable = Array.from(document.querySelectorAll('table')).find(table => {
                return table.innerText.includes("Permit Number");
            });
            if (!permitTable) return [];

            return Array.from(permitTable.querySelectorAll('tbody tr')).map(row => {
                const cells = row.querySelectorAll('td');
                return {
                    description: cells[1]?.textContent.trim(),
                    issue_date: cells[2]?.textContent.trim(),
                    value: cells[3]?.textContent.trim(),
                };
            });
        }''')

        time.sleep(10)  # Respect crawl delay

        try:
            page.close()
            browser.close()
        except Exception as e:
            print(f"Error closing browser: {e}")

        print(f"Session replay: https://browserbase.com/sessions/{session.id}")
        return {**parsed_data, "permits": permits}


def parse_owner_and_address_data(data):
    """
    Parse owner name and address data according to user specifications
    """
    result = {}
    
    # Parse owner name with specific logic
    raw_owner = data.get('raw_owner', '') or ''
    
    if not raw_owner.strip():
        result['first_name'] = ''
        result['last_name'] = ''
    else:
        # Split by <br> tags to handle multiple names
        names = [name.strip() for name in raw_owner.split('<br') if name.strip()]
        names = [name.lstrip('/>').strip() for name in names]  # Clean up potential tag remnants
        names = [name for name in names if name]  # Remove empty strings
        
        first_names = []
        last_names = []
        
        for name in names:
            if ',' in name:
                # Split by comma: before comma = last name, after comma = first name
                parts = name.split(',', 1)
                last_name = parts[0].strip()
                first_name = parts[1].strip() if len(parts) > 1 else ''
                
                if last_name:
                    last_names.append(last_name)
                if first_name:
                    first_names.append(first_name)
            else:
                # No comma = company name, put all in first name
                if name.strip():
                    first_names.append(name.strip())
        
        # Join multiple names with " / "
        result['first_name'] = ' / '.join(first_names) if first_names else ''
        result['last_name'] = ' / '.join(last_names) if last_names else ''
    
    # Parse address into components
    address = data.get('address', '') or ''
    result['address_1'] = ''
    result['city'] = ''
    result['state'] = ''
    result['zip'] = ''
    
    if address.strip():
        # Check if address has <br> tags separating street address from city/state/zip
        if '<br' in address:
            # Split by <br> tags
            address_parts = [part.strip() for part in address.split('<br') if part.strip()]
            address_parts = [part.lstrip('/>').strip() for part in address_parts]  # Clean up potential tag remnants
            address_parts = [part for part in address_parts if part]  # Remove empty strings
            
            if len(address_parts) >= 2:
                # First part is Address 1 (street address)
                result['address_1'] = address_parts[0].strip()
                
                # Second part contains City, State, Zip
                city_state_zip_line = address_parts[1].strip()
                
                # Parse city, state, zip from the second line
                # Expected format: "City, State Zip" or "City, State Zip-extension"
                if ',' in city_state_zip_line:
                    city_part, state_zip_part = city_state_zip_line.split(',', 1)
                    result['city'] = city_part.strip()
                    
                    # Parse state and zip from remaining part
                    state_zip_parts = state_zip_part.strip().split()
                    if len(state_zip_parts) >= 2:
                        # First part should be state (2-letter code)
                        potential_state = state_zip_parts[0]
                        if len(potential_state) == 2 and potential_state.isalpha():
                            result['state'] = potential_state.upper()
                        
                        # Look for zip code in remaining parts
                        for part in state_zip_parts[1:]:
                            # Check if it looks like a zip code (5 digits or 5-4 format)
                            if re.match(r'^\d{5}(-\d{4})?$', part):
                                result['zip'] = part
                                break
                    elif len(state_zip_parts) == 1:
                        # Could be state or zip
                        part = state_zip_parts[0]
                        if len(part) == 2 and part.isalpha():
                            result['state'] = part.upper()
                        elif re.match(r'^\d{5}(-\d{4})?$', part):
                            result['zip'] = part
                else:
                    # No comma in second line, try to parse differently
                    # Look for state and zip patterns
                    state_match = re.search(r'\b([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', city_state_zip_line)
                    if state_match:
                        result['state'] = state_match.group(1)
                        result['zip'] = state_match.group(2)
                        # Everything before state is city
                        result['city'] = city_state_zip_line[:state_match.start()].strip()
                    else:
                        # Put everything in city if can't parse
                        result['city'] = city_state_zip_line
            elif len(address_parts) == 1:
                # Only one part, put it in address_1
                result['address_1'] = address_parts[0].strip()
        else:
            # No <br> tags - fall back to previous parsing logic
            # Try to parse address - typical format: "123 Main St, City, State Zip"
            if ',' in address:
                parts = [part.strip() for part in address.split(',')]
                if len(parts) >= 3:
                    result['address_1'] = parts[0]
                    result['city'] = parts[1]
                    # Parse state and zip from last part
                    last_part = parts[2]
                    state_zip_parts = last_part.split()
                    if len(state_zip_parts) >= 2:
                        result['state'] = state_zip_parts[0]
                        result['zip'] = ' '.join(state_zip_parts[1:])
                    elif len(state_zip_parts) == 1:
                        # Could be state or zip
                        if state_zip_parts[0].isdigit() or '-' in state_zip_parts[0]:
                            result['zip'] = state_zip_parts[0]
                        else:
                            result['state'] = state_zip_parts[0]
                elif len(parts) == 2:
                    result['address_1'] = parts[0]
                    # Try to parse city, state, zip from second part
                    second_part = parts[1].split()
                    if len(second_part) >= 3:
                        result['city'] = ' '.join(second_part[:-2])
                        result['state'] = second_part[-2]
                        result['zip'] = second_part[-1]
                    elif len(second_part) == 2:
                        result['city'] = second_part[0]
                        # Could be state or zip
                        if second_part[1].isdigit() or '-' in second_part[1]:
                            result['zip'] = second_part[1]
                        else:
                            result['state'] = second_part[1]
                    else:
                        result['city'] = parts[1]
            else:
                # No commas - try to parse by common patterns
                # Look for zip code (digits, possibly with dash)
                zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', address)
                if zip_match:
                    result['zip'] = zip_match.group(1)
                    # Remove zip from address for further parsing
                    address_without_zip = address.replace(zip_match.group(1), '').strip()
                    
                    # Look for state (2-letter code before zip)
                    state_match = re.search(r'\b([A-Z]{2})\s*$', address_without_zip)
                    if state_match:
                        result['state'] = state_match.group(1)
                        address_without_state = address_without_zip.replace(state_match.group(1), '').strip()
                        
                        # Split remaining into address and city
                        remaining_parts = address_without_state.split()
                        if len(remaining_parts) >= 3:
                            # Assume first 3+ words are address, rest is city
                            result['address_1'] = ' '.join(remaining_parts[:3])
                            result['city'] = ' '.join(remaining_parts[3:])
                        else:
                            result['address_1'] = address_without_state
                    else:
                        result['address_1'] = address_without_zip
                else:
                    # No clear zip pattern, put everything in address_1
                    result['address_1'] = address
    
    # Add other fields from original data
    result['use_code'] = data.get('use_code')
    result['roof_cover'] = data.get('roof_cover')
    result['living_sf'] = data.get('living_sf')
    result['year_built'] = data.get('year_built')
    
    return result


def calculate_roof_age(property_data):
    now = datetime.now()
    roof_type = (property_data['roof_cover'] or "").lower()
    
    # Define thresholds
    roof_thresholds = {
        "shingle": 15,
        "concrete tile": 20,
        "metal": 20,
        "roll": 15,
        "tar": 15,
        "gravel": 15,
    }

    # Try to find best threshold match
    threshold = None
    for key, value in roof_thresholds.items():
        if key in roof_type:
            threshold = value
            break

    # Check permits
    roof_permits = [
        p for p in property_data["permits"] if "roof" in p["description"].lower()
    ]
    
    age = None
    roof_age_display = "Unknown"
    
    if roof_permits:
        latest = max(roof_permits, key=lambda p: datetime.strptime(p['issue_date'], "%m/%d/%Y"))
        age = (now - datetime.strptime(latest['issue_date'], "%m/%d/%Y")).days / 365.25
        years = int(round(age))
        roof_age_display = f"{years} years ({latest['issue_date']})"
    else:
        # Fallback to year built
        if property_data['year_built']:
            age = now.year - int(property_data['year_built'])
            years = int(age)
            roof_age_display = f"{years} years (built {property_data['year_built']})"

    if age is not None and threshold:
        passed = age >= threshold
    else:
        passed = False

    return {
        "roof_age": roof_age_display,
        "material_type": roof_type,
        "pass": passed,
    }


if __name__ == "__main__":
    # Test Parcel ID
    parcel_id = "153022799200100010"
    prop = extract_property_data(parcel_id)
    analysis = calculate_roof_age(prop)
    
    print("\nExtracted Info:")
    print(f"STRAP: {parcel_id}")
    print(f"First Name: {prop.get('first_name')}")
    print(f"Last Name: {prop.get('last_name')}")
    print(f"Address 1: {prop.get('address_1')}")
    print(f"City: {prop.get('city')}")
    print(f"State: {prop.get('state')}")
    print(f"Zip: {prop.get('zip')}")
    print(f"Property Use: {prop.get('use_code')}")
    print(f"Roof Cover: {prop.get('roof_cover')}")
    print(f"Living SF: {prop.get('living_sf')}")
    print(f"Year Built: {prop.get('year_built')}")
    print(f"\nPermits Found: {len(prop['permits'])}")
    print("Roof Age Analysis:", analysis)
