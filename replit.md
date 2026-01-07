# Ticket Agency Management System

## Overview

This is a Ticket Agency Management System built with Python and Streamlit. The application connects to a Google Sheet ("מערכת הזמנות - קוד יהודה") to manage ticket orders, track purchasing status, monitor profitability, and provide operational insights for upcoming events.

The system provides:
- Real-time order management with Google Sheets integration
- Smart date parsing for mixed date formats
- Purchasing workflow with bulk status updates
- Profit analytics and visualization
- Operational alerts for time-sensitive orders
- Source name standardization and comparison
- Category summary with visual breakdowns
- Advanced search with copy functionality

## User Preferences

Preferred communication style: Simple, everyday language (Hebrew).

## Recent Changes (January 2026)

### Automatic Email Reports
- Added email scheduler system with APScheduler
- Four scheduled reports:
  - 10:00 AM: Unpaid orders reminder (sent - not paid status)
  - 10:05 AM: Daily sales report
  - 20:00: Daily new orders report
  - Sunday 09:00: Weekly sales summary
- New "📧 מיילים אוטומטיים" tab for manual sending and status monitoring
- Scripts: email_scheduler.py, daily_reminder.py, daily_sales_report.py, daily_new_orders_report.py, weekly_sales_report.py
- Resend integration for email delivery

### New Orders Tab Enhancement
- Added order date display alongside event date
- Light blue highlighting for orders with "orderd" status
- Delete button functionality
- Direct Google Sheets data loading (bypasses sidebar filters)

## Recent Changes (December 2025)

### Category Summary Feature
- Added expandable category summary above each event's order details
- Color-coded progress bars for each category (CAT 1/2: Blue, CAT 3/4: Yellow, Premium/VIP: Green, LONGSIDE/TIER: Red)
- Shows ticket count, percentage, and financial breakdown per category

### Enhanced Event Details Table
- Added columns: Order Number, Category/Section, Seating Arrangements, Supplier Order Number
- Hebrew column headers for better readability
- Replaced row index with Order Number for easier identification

### Source Name Standardization
- SOURCE_DISPLAY_NAMES dictionary for consistent display (e.g., goldenseat → Goldenseat/TikTik)
- Case-insensitive grouping in filters and Source Comparison tab

### Copy Functionality
- Quick Copy section with st.code() for native clipboard support
- Displays Order Number, Event Name, Docket Number, Supplier Order Number

### Search Enhancement
- Searches both Order Number and Docket Number
- "Found In" indicator showing which field matched
- Clickable results list for multiple matches

## System Architecture

### Frontend Architecture
- **Framework**: Streamlit (Python-based web framework)
- **Layout**: Wide layout configuration for data-heavy views
- **Components**: 
  - Sidebar for filtering (event name, date range, source, team, supplier)
  - Tab-based navigation for different functional areas
  - Alert badges for time-sensitive notifications
  - Interactive data tables with row selection capabilities
  - Category summary expanders with progress bars

### Data Layer
- **Primary Data Source**: Google Sheets via gspread library
- **Data Processing**: Pandas DataFrames for in-memory manipulation
- **Row Index Tracking**: Original Google Sheet row numbers preserved for write-back operations
- **Caching**: Streamlit caching for performance optimization
- **Currency Conversion**: Real-time rates via exchangerate-api.com

### Authentication & Authorization
- **Method**: Google Service Account credentials
- **Credential Storage**: Streamlit secrets (`st.secrets["GOOGLE_CREDENTIALS"]`)
- **Scopes**: Google Sheets API and Google Drive API access

### Key Design Patterns
- **Read-Write Pattern**: Load data into DataFrame, process locally, write back specific cells via gspread
- **Smart Date Parsing**: Multi-format date parser with context-aware disambiguation using event names
- **Data Cleaning Pipeline**: Automatic whitespace stripping, currency symbol removal, type conversion
- **Fuzzy Event Matching**: Groups similar event names with fuzzy string matching
- **Source Normalization**: Standardizes source names for consistent grouping

### Tab Structure
1. **Purchasing Center (מרכז קניות)**: Actionable view for marking orders as purchased, with category summary
2. **Profit Intelligence (אנליטיקות רווח)**: Analytics dashboard with metrics and charts
3. **Operational View (תצוגה תפעולית)**: 7-day lookahead for upcoming events
4. **New Orders (הזמנות חדשות)**: Orders with "new" status for processing
5. **Sales (מכירות)**: Daily, weekly and monthly sales tracking
6. **Source Comparison (השוואת מקורות)**: Revenue and profit analysis by sales source
7. **Automatic Emails (מיילים אוטומטיים)**: Email scheduler status and manual sending

## External Dependencies

### Google Services
- **Google Sheets API**: Primary data storage and synchronization
- **Google Drive API**: Required for sheet access
- **Sheet Name**: "מערכת הזמנות - קוד יהודה  " (Worksheet index 0)

### Python Libraries
- **gspread**: Google Sheets read/write operations
- **oauth2client**: Service account authentication
- **pandas**: Data manipulation and processing
- **plotly**: Interactive charts (express and graph_objects)
- **streamlit**: Web application framework
- **pytz**: Timezone handling
- **requests**: API calls for currency rates

### Configuration
- **Secrets Required**: `GOOGLE_CREDENTIALS` containing service account JSON
- **Expected Columns**: 'event name', 'Date of the event', 'Category / Section', 'Seating Arrangements', 'Order number', 'SUPP order number', 'Status', 'orderd', 'TOTAL', 'SUPP PRICE', 'source', 'Supplier NAME', 'Qty'

## Key Functions

### Category Display
- `get_category_color(category)`: Returns color emoji based on category type
- `display_category_summary(orders_df)`: Renders expandable category breakdown

### Source Normalization
- `normalize_source_name(source)`: Normalizes source for grouping
- `get_source_display_name(source)`: Returns user-friendly display name
- `SOURCE_DISPLAY_NAMES`: Dictionary mapping normalized names to display names

### Event Grouping
- `group_orders_by_event(df)`: Groups orders with fuzzy matching
- `are_same_event(event1, event2, date1, date2)`: Compares events for similarity
- `normalize_team_name(name)`: Normalizes team names preserving key words
