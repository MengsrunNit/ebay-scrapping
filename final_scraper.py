"""
Final working eBay scraper using the playwright_rendered.html file
"""
from bs4 import BeautifulSoup
import pandas as pd

def parse_ebay_html(filename='playwright_rendered.html'):
    with open(filename, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the results list
    results = soup.find('ul', {'class': 'srp-results'})
    if not results:
        print("No results list found!")
        return []
    
    items = results.find_all('li')
    print(f"Found {len(items)} total items")
    
    items_data = []
    for idx, item in enumerate(items, 1):
        try:
            # Extract title from heading
            title_elem = item.find('div', {'role': 'heading'})
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True).replace('Opens in a new window or tab', '').strip()
            
            # Extract price
            price_elem = item.find('span', class_='s-card__price')
            price = price_elem.get_text(strip=True) if price_elem else 'N/A'
            
            # Extract link
            link_elem = item.find('a', href=lambda x: x and '/itm/' in x if x else False)
            if not link_elem:
                continue
            link = link_elem.get('href', '').split('?')[0]
            
            # Extract image
            img_elem = item.find('img')
            image_url = img_elem.get('src', 'N/A') if img_elem else 'N/A'
            
            items_data.append({
                'Title': title,
                'Price': price,
                'Link': link,
                'Image Link': image_url
            })
            
        except Exception as e:
            print(f"Error parsing item {idx}: {e}")
            continue
    
    return items_data

if __name__ == "__main__":
    print("Parsing eBay HTML...\n")
    items = parse_ebay_html()
    
    if items:
        print(f"\n✓ Successfully parsed {len(items)} items")
        
        # Save to CSV
        df = pd.DataFrame(items)
        df.to_csv('ebay_final_results.csv', index=False)
        print(f"✓ Saved to ebay_final_results.csv")
        
        # Show sample
        print("\nFirst 5 items:")
        for i, item in enumerate(items[:5], 1):
            print(f"\n{i}. {item['Title'][:80]}")
            print(f"   Price: {item['Price']}")
            print(f"   Link: {item['Link'][:60]}...")
    else:
        print("\n✗ No items found")
