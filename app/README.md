# Venue Intelligence MVP

A simple web interface for exploring and exporting venue data.

## Run Locally

```bash
cd venue-intel
streamlit run app/venue_intel_app.py
```

Opens at: http://localhost:8501

## Features

1. **Overview** - Database statistics and distribution charts
2. **Explore Venues** - Filter by city, type, score, tiers
3. **Export Data** - Download filtered data as CSV/Excel
4. **Request New City** - Cost estimates for new city data (disabled by default)

## Deploy to Streamlit Cloud

1. Push to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/venue-intel.git
   git push -u origin main
   ```

2. Go to [share.streamlit.io](https://share.streamlit.io)

3. Connect your GitHub repo

4. Set:
   - Main file: `app/venue_intel_app.py`
   - Python version: 3.11+

5. Deploy

## Data

The app reads from `data/processed/venue_intelligence.db` (SQLite).

For Streamlit Cloud deployment, you'll need to either:
- Include the database in the repo (current: 20MB)
- Or connect to a hosted database (future enhancement)

## Cost Controls

The "Request New City" feature is disabled by default to prevent accidental API costs.
Enable by modifying the `disabled=True` parameter in the app.
