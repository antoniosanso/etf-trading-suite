
import os
import pandas as pd

def finalize_signals(res_entries, cfg, outdir):
    """Robust finalization of signals DataFrame with safe RankScore handling."""
    df = pd.DataFrame(res_entries)

    # 1) Find available ranking column
    score_candidates = ['RankScore', 'rank_score', 'score']
    score_col = next((c for c in score_candidates if c in df.columns), None)

    # 2) Rebuild from rank_weights if missing
    if score_col is None:
        rs = 0.0
        weights = (cfg.get('rank_weights') or {})
        if weights:
            for k, w in weights.items():
                if k in df.columns:
                    rs = rs + (df[k].fillna(0.0) * float(w))
        df['RankScore'] = rs if isinstance(rs, pd.Series) else 0.0
        score_col = 'RankScore'

    # 3) Safe default for top_n
    top_n = int(cfg.get('top_n', 10))

    # 4) Output file creation
    os.makedirs(os.path.join(outdir, 'signals'), exist_ok=True)
    (df.sort_values(score_col, ascending=False)
       .head(top_n)
       .to_csv(os.path.join(outdir, 'signals', 'entries_today.csv'), index=False))

    return df
