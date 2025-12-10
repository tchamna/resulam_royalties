# Resulam Royalties Dashboard

A modern, interactive dashboard for analyzing book sales and royalties data from Amazon KDP.

## 🚀 Features

- **Interactive Dashboard**: Modern Dash-based web interface with Bootstrap styling
- **Sales Analytics**: Visualize sales trends by year, language, and book
- **Author Analysis**: Track individual author contributions and royalties
- **Geographic Distribution**: Analyze sales across different marketplaces
- **Data Export**: Automatically exports processed data to CSV files
- **Modular Architecture**: Clean, maintainable code structure

## 📁 Project Structure

```
resulam_royalties/
├── src/
│   ├── config.py              # Configuration and constants
│   ├── data/
│   │   ├── __init__.py
│   │   └── processor.py       # Data loading and processing
│   ├── visualization/
│   │   ├── __init__.py
│   │   └── charts.py          # Chart generation functions
│   ├── dashboard/
│   │   ├── __init__.py
│   │   └── app.py             # Dash dashboard application
│   └── utils/
│       ├── __init__.py
│       └── helpers.py         # Utility functions
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## 🛠️ Installation

### Prerequisites
- Python 3.11 or higher
- pip or uv package manager

### Setup

1. **Clone or navigate to the project directory**
   ```bash
   cd C:\Users\tcham\Wokspace\resulam_royalties
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   # Using uv (faster)
   uv venv

   # Or using standard venv
   python -m venv venv
   ```

3. **Activate the virtual environment**
   ```powershell
   # On Windows PowerShell
   .\venv\Scripts\Activate.ps1
   ```

4. **Install dependencies**
   ```bash
   # Using uv
   uv pip install -r requirements.txt

   # Or using pip
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

Update the data file paths in `src/config.py`:

```python
# Update these paths to match your data location
MAIN_DIR = r"G:\My Drive\Mbú'ŋwɑ̀'nì\RoyaltiesResulam"
BOOKS_DATABASE_PATH = Path(MAIN_DIR) / "Resulam_books_database_Amazon_base_de_donnee_livres.csv"
ROYALTIES_HISTORY_PATH = Path(MAIN_DIR) / f"KDP_OrdersResulamBookSales2015_{LAST_YEAR}RoyaltiesReportsHistory.xlsx"
```

## 🎯 Usage

### Start the Dashboard

```bash
python main.py
```

The dashboard will start on `http://localhost:8050`

### Features Available

1. **Sales Overview Tab**
   - Yearly sales trends
   - Sales by language (stacked/grouped views)

2. **Books Analysis Tab**
   - Total sales by book title
   - Yearly breakdown with interactive filters

3. **Authors Analysis Tab**
   - Top authors by royalties
   - Top authors by books sold
   - Author statistics summary

4. **Geographic Distribution Tab**
   - Sales distribution by marketplace
   - Revenue by marketplace

## 📊 Data Processing

The application automatically:

1. **Loads** data from Excel/CSV files
2. **Cleans** and normalizes author names and book titles
3. **Classifies** books by language
4. **Calculates** royalties and author shares
5. **Exports** processed data to CSV files:
   - `royalties_resulambooks_from_2015_YYYY_history_df.csv`
   - `royalties_exploded_YYYY.csv`
   - `royalties_per_author_YYYY.csv`

## 🔧 Technical Stack

- **Python 3.11+**
- **Pandas**: Data processing and analysis
- **Plotly**: Interactive visualizations
- **Dash**: Web dashboard framework
- **Dash Bootstrap Components**: UI components
- **OpenpyXL**: Excel file handling

## 📝 Key Improvements Over Original

1. **Modular Design**: Separated concerns into logical modules
2. **Type Hints**: Added type annotations for better code clarity
3. **Error Handling**: Robust error handling and validation
4. **Configuration Management**: Centralized configuration
5. **Modern UI**: Bootstrap-based responsive design
6. **Clean Code**: PEP 8 compliant, well-documented
7. **Scalability**: Easy to extend with new features
8. **Performance**: Optimized data processing pipeline

## 🎨 Customization

### Adding New Visualizations

Add new chart methods to `src/visualization/charts.py`:

```python
class SalesCharts:
    @staticmethod
    def your_new_chart(df: pd.DataFrame) -> go.Figure:
        # Your chart logic here
        return fig
```

### Modifying Dashboard Layout

Edit `src/dashboard/app.py` to customize:
- Metrics cards
- Tab structure
- Color scheme
- Layout components

### Adding Data Sources

Extend `src/data/processor.py`:

```python
@staticmethod
def load_new_data_source(path: Path) -> pd.DataFrame:
    # Your data loading logic
    return df
```

## 🐛 Troubleshooting

### Import Errors
Make sure you're in the project root directory and have activated the virtual environment.

### Data File Not Found
Check that paths in `src/config.py` match your actual file locations.

### Port Already in Use
Change the port in `src/config.py`:
```python
DASHBOARD_CONFIG = {
    'port': 8051,  # Change to any available port
    ...
}
```

## 📄 License

This project is proprietary software for Resulam Books.

## 👥 Authors

- Dashboard Development: Refactored and modernized version
- Original Script: Resulam Team

## 📮 Support

For issues or questions, please contact the development team.

---

Built with ❤️ for Resulam Books
