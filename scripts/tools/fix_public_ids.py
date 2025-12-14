
import re

file_path = r"C:\Users\tcham\Wokspace\resulam_royalties\src\dashboard\public.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

ids_to_replace = [
    "theme-icon", "theme-toggle-btn", "theme-store", "header-container",
    "year-filter", "year-filter-store", "language-label", "language-filter",
    "author-label", "author-filter", "booktype-label", "booktype-filter",
    "book-label", "book-filter", "category-label", "category-filter",
    "reset-all-filters", "metric-books-sold", "metric-titles", "metric-authors",
    "sales-trend-title", "loading-trend-chart", "sales-trend-chart",
    "sales-language-display-mode", "loading-sales-chart", "sales-by-language-chart",
    "sales-overview-section", "dashboard-tabs", "tab-content",
    "refresh-interval", "reload-state", "data-refresh-signal", "data-update-toast",
    "author-selector-dropdown", "clear-all-btn", "add-all-btn",
    "download-csv-btn", "download-txt-btn", "download-csv", "download-txt",
    "author-trends-graph", "download-authors-earnings-csv",
    "download-authors-earnings-txt", "download-authors-adjustment-csv",
    "download-authors-adjustment-txt", "download-purchase-csv-btn",
    "download-purchase-excel-btn", "download-purchase-txt-btn",
    "download-purchase-csv", "download-purchase-excel", "download-purchase-txt",
    "purchase-download-data", "returns-modal", "returns-details-btn",
    "returns-close-btn", "returns-table-content",
    "download-authors-alpha-csv", "download-authors-alpha-txt"
]

new_content = content
for old_id in ids_to_replace:
    # Replace id="old_id"
    new_content = new_content.replace(f'id="{old_id}"', f'id="public-{old_id}"')
    new_content = new_content.replace(f"id='{old_id}'", f"id='public-{old_id}'")
    
    # Replace Input("old_id"
    new_content = new_content.replace(f'Input("{old_id}"', f'Input("public-{old_id}"')
    new_content = new_content.replace(f"Input('{old_id}'", f"Input('public-{old_id}'")
    
    # Replace Output("old_id"
    new_content = new_content.replace(f'Output("{old_id}"', f'Output("public-{old_id}"')
    new_content = new_content.replace(f"Output('{old_id}'", f"Output('public-{old_id}'")
    
    # Replace State("old_id"
    new_content = new_content.replace(f'State("{old_id}"', f'State("public-{old_id}"')
    new_content = new_content.replace(f"State('{old_id}'", f"State('public-{old_id}'")
    
    # Replace tab_id="old_id" (for tabs) - wait, tabs use tab_id, not id.
    # The tabs are "purchase", "sales", "books", "geography". These are values, not component IDs.
    # But "dashboard-tabs" is an ID.
    
    # Also replace usage in callbacks where ID is passed as string literal?
    # e.g. if button_id == 'clear-all-btn':
    new_content = new_content.replace(f"== '{old_id}'", f"== 'public-{old_id}'")
    new_content = new_content.replace(f'== "{old_id}"', f'== "public-{old_id}"')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully updated IDs in public.py")
