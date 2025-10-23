"""
Scrape eBay search results using Playwright (handles dynamic JavaScript content)
"""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

def scrape_ebay_with_playwright(max_pages=3):
    """
    Scrape multiple pages of eBay results
    max_pages: Number of pages to scrape (default: 3)
    """
    with sync_playwright() as p:
        # Launch browser with anti-detection settings
        print("Launching browser...")
        browser = p.chromium.launch(
            headless=False,  # Set to True to hide browser
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        # Build search URL base
        base_url = "https://www.ebay.com/sch/i.html"
        
        all_items = []
        
        # Loop through pages
        for page_num in range(1, max_pages + 1):
            print(f"\n{'='*60}")
            print(f"Scraping Page {page_num}/{max_pages}...")
            print(f"{'='*60}")
            
            # Build URL with page number
            params = [
                "_nkw=pixel+9+pro+xl",
                "_sacat=0",
                "_from=R40",
                "LH_Sold=1",
                "LH_Complete=1",
                "rt=nc",
                "LH_ItemCondition=2010|2020|2030",
                "Network=Unlocked",
                "_dcat=9355",
                "_ipg=240",
                f"_pgn={page_num}"
            ]
            search_url = f"{base_url}?{'&'.join(params)}"
            
            try:
                print(f"Navigating to page {page_num}...")
                page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for results to load
                print("Waiting for results...")
                time.sleep(3)
                
                try:
                    page.wait_for_selector("ul.srp-results", timeout=15000)
                    print("✓ Results loaded")
                except:
                    print("⚠️ Could not find results. Saving debug files...")
                    page.screenshot(path=f"debug_page_{page_num}.png")
                    with open(f"debug_page_{page_num}.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                    print(f"   Saved: debug_page_{page_num}.png and debug_page_{page_num}.html")
                    break
                
                # Get page content
                html_content = page.content()
                
                # Save first page for inspection
                if page_num == 1:
                    with open("playwright_rendered.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print("✓ Saved first page to playwright_rendered.html")
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Find results using the working selector from final_scraper.py
                results_list = soup.find('ul', {'class': 'srp-results'})
                if not results_list:
                    print("❌ No results list found")
                    break
                
                items = results_list.find_all('li')
                print(f"Found {len(items)} total items on page")
                
                # Extract data
                page_items = 0
                for item in items:
                    try:
                        # Extract title from heading (the working method!)
                        title_elem = item.find('div', {'role': 'heading'})
                        if not title_elem:
                            continue
                        title = title_elem.get_text(strip=True).replace('Opens in a new window or tab', '').strip()
                        
                        if not title or len(title) < 10:
                            continue
                        
                        # Extract price
                        price_elem = item.find('span', class_='s-card__price')
                        price = price_elem.get_text(strip=True) if price_elem else 'N/A'
                        
                        # Extract sold date
                        sold_date = 'N/A'
                        # Look for sold date in various possible locations
                        sold_date_elem = (
                            item.find('span', class_='POSITIVE') or  # Common class for sold date
                            item.find('span', string=lambda x: x and 'Sold' in x if x else False) or
                            item.find('span', class_=lambda x: x and 'sold' in ' '.join(x).lower() if x else False)
                        )
                        if sold_date_elem:
                            sold_date = sold_date_elem.get_text(strip=True)
                        
                        # Extract link
                        link_elem = item.find('a', href=lambda x: x and '/itm/' in x if x else False)
                        if not link_elem:
                            continue
                        link = link_elem.get('href', '').split('?')[0]
                        
                        # Extract image
                        img_elem = item.find('img')
                        image_url = img_elem.get('src', 'N/A') if img_elem else 'N/A'
                        
                        all_items.append({
                            'Page': page_num,
                            'Title': title,
                            'Price': price,
                            'Sold Date': sold_date,
                            'Link': link,
                            'Image Link': image_url
                        })
                        page_items += 1
                        
                    except Exception as e:
                        continue
                
                print(f"✓ Extracted {page_items} items from page {page_num}")
                print(f"✓ Total items so far: {len(all_items)}")
                
                # Check for next page
                if page_num < max_pages:
                    next_button = soup.find('a', class_='pagination__next')
                    if not next_button or 'pagination__next--disabled' in ' '.join(next_button.get('class', [])):
                        print("\n✓ Reached last page!")
                        break
                    
                    delay = random.uniform(3, 6)
                    print(f"⏳ Waiting {delay:.1f} seconds before next page...")
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"❌ Error on page {page_num}: {e}")
                break
        
        # Close browser
        browser.close()
        return all_items

if __name__ == "__main__":
    print("Starting eBay Multi-Page Scraper with Playwright...\n")
    
    # Scrape 3 pages (should get ~500 items with _ipg=240)
    items = scrape_ebay_with_playwright(max_pages=3)
    
    if items:
        print(f"\n{'='*60}")
        print(f"✅ SCRAPING COMPLETE!")
        print(f"{'='*60}")
        print(f"Total items scraped: {len(items)}")
        
        # Save to CSV
        df = pd.DataFrame(items)
        df.to_csv('ebay_playwright_results.csv', index=False)
        print(f"✓ Saved to ebay_playwright_results.csv")
        
        # Show statistics
        print(f"\nItems per page:")
        for page_num in sorted(df['Page'].unique()):
            count = len(df[df['Page'] == page_num])
            print(f"  Page {page_num}: {count} items")
        
        # Show sample
        print(f"\nFirst 5 items:")
        for i, item in enumerate(items[:5], 1):
            print(f"\n{i}. {item['Title'][:70]}")
            print(f"   Price: {item['Price']}")
            print(f"   Sold Date: {item['Sold Date']}")
            print(f"   Page: {item['Page']}")
    else:
        print("\n❌ No items scraped")
        print("Check debug files if created: debug_page_1.png, debug_page_1.html")
