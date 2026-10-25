# Website screenshot capture checklist

No valid screenshots are currently stored here. The integrated screenshot attempts during documentation work produced incomplete/blank images, so those files were removed instead of being shown as website evidence.

## Capture genuine screenshots

1. Start GreenPulse Pune from the repository root:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   streamlit run app.py
   ```

2. Open `http://localhost:8501` in Microsoft Edge or Chrome at a desktop size (for example, 1440 × 1000). Use 100% browser zoom. Ensure the MySQL state and synthetic-data badge are visible where relevant.
3. Use the actual Streamlit sidebar to open each screen. Scroll to the relevant section before capturing. Do not use an AI-generated mockup or a locally generated data chart as a website screenshot.
4. Save captures with these names when the corresponding screen exists:

   - `01_pune_overview.png`
   - `02_heat_hotspots.png`
   - `03_air_quality.png`
   - `04_electricity_hotspots.png`
   - `05_zone_explorer.png`
   - `06_ml_predictions.png`
   - `07_data_pipeline_status.png`

5. In Windows, `Win+Shift+S` can capture the visible app area. Save the PNG files into this directory. Prefer hiding browser chrome with full-screen mode and avoid capturing credentials or configuration.
6. Confirm each image visibly matches its page and contains no secrets. Then embed only selected screenshots in the root README, this directory's documentation, and [Results and Findings](../14_RESULTS_AND_FINDINGS.md), with captions that identify synthetic, simulated, or provider-estimated values.

Do not label a screenshot as an Air Quality or ML results page unless that actual page is open in the running application. The bundled dashboard can display synthetic demo values; the screenshot caption must say so.
