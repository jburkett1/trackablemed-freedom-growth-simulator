# TrackableMed Freedom Growth Economics App

Interactive Streamlit ROI simulator for Curonix Freedom PNS physician-owned ASC growth discussions.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Create a private GitHub repo.
2. Upload `app.py`, `requirements.txt`, and the `assets` folder.
3. Go to Streamlit Cloud and choose **New app**.
4. Select the repo, branch, and `app.py`.
5. Deploy.

## Notes

This calculator uses Medicare national average reimbursement assumptions from the Curonix 2026 billing guide and editable default cost assumptions. It is for business planning only, not reimbursement advice. Providers are responsible for final coding, billing, medical necessity, documentation, and payer verification.
