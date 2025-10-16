
# --- PATCH: robust RankScore handling (append near the DataFrame build) ---
def _finalize_and_write(res_entries, cfg, outdir):
    import pandas as pd
    df = pd.DataFrame(res_entries)
    # Harmonize column names
    if 'RankScore' not in df.columns and 'rank_score' in df.columns:
        df = df.rename(columns={'rank_score': 'RankScore'})
    # If still missing, try to compute from momentum weights if present
    if 'RankScore' not in df.columns:
        try:
            w = cfg.get('rank_weights', {})
            mom_cols = [c for c in df.columns if c.lower().startswith('mom')]
            if w and mom_cols:
                rs = 0.0
                for k, wt in w.items():
                    col = k  # e.g., 'mom252', 'mom63'
                    if col in df.columns:
                        rs = rs + wt * df[col].fillna(0.0)
                df['RankScore'] = rs
        except Exception:
            pass
    # Ensure top_n exists
    top_n = int(cfg.get('top_n', 10))
    df.sort_values('RankScore', ascending=False).head(top_n).to_csv(
        os.path.join(outdir, 'signals', 'entries_today.csv'), index=False
    )
    return df
# --- END PATCH ---
