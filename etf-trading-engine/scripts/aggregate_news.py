import argparse, yaml, pandas as pd, numpy as np, re
from datetime import datetime
from pathlib import Path
def try_imports():
    import importlib; mods = {}
    for m in ["feedparser", "requests", "vaderSentiment.vaderSentiment"]:
        try: mods[m] = importlib.import_module(m)
        except Exception: mods[m] = None
    return mods
MODS = try_imports()
feedparser = MODS.get("feedparser"); requests = MODS.get("requests")
vader_mod = MODS.get("vaderSentiment.vaderSentiment")
SentimentIntensityAnalyzer = getattr(vader_mod, "SentimentIntensityAnalyzer", None) if vader_mod else None
def clean(x): return re.sub(r"\s+"," ",x).strip() if isinstance(x,str) else ""
def fetch_rss(url, k=50):
    out = []; 
    if not feedparser: return out
    try:
        fp = feedparser.parse(url)
        for e in fp.get("entries", [])[:k]:
            out.append({"source":"rss","url":url,"title":clean(e.get("title","")),"desc":clean(e.get("summary","") or e.get("description","")),"link":e.get("link",""),"published":e.get("published","")})
    except Exception: pass
    return out
def fetch_google(q, k=20):
    if not feedparser: return []
    import urllib.parse as up
    url = f"https://news.google.com/rss/search?q={up.quote(q)}&hl=en-US&gl=US&ceid=US:en"
    try:
        fp = feedparser.parse(url)
        return [{"source":"google","url":url,"title":clean(e.get("title","")),"desc":clean(e.get("summary","")),"link":e.get("link",""),"published":e.get("published","")} for e in fp.get("entries", [])[:k]]
    except Exception: return []
def fetch_gdelt(q, k=30):
    if not requests: return []
    try:
        r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params={"query":q,"mode":"ArtList","format":"JSON","maxrecords":str(k*2)}, timeout=20)
        data = r.json(); items = []
        for d in data.get("articles", [])[:k]:
            items.append({"source":"gdelt","url":"gdelt","title":clean(d.get("title","")),"desc":clean(d.get("seendate","")),"link":d.get("url",""),"published":d.get("seendate","")})
        return items
    except Exception: return []
def sentiment(txt):
    if not SentimentIntensityAnalyzer: return 0.0
    sid = SentimentIntensityAnalyzer(); return float(sid.polarity_scores(txt or "").get("compound",0.0))
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", required=True); ap.add_argument("--universe", required=True)
    ap.add_argument("--topics", required=True); ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.sources,"r",encoding="utf-8"))
    uni = pd.read_csv(args.universe); uni["Ticker"]=uni["Ticker"].astype(str)
    items = []; 
    for u in cfg.get("rss",[]) or []: items += fetch_rss(u)
    for q in cfg.get("google_news_queries",[]) or []: items += fetch_google(q)
    if cfg.get("gdelt_enabled", False):
        for q in cfg.get("gdelt_topics",[]) or []: items += fetch_gdelt(q)
    df = pd.DataFrame(items); Path(args.outdir).mkdir(parents=True, exist_ok=True)
    if df.empty:
        pd.DataFrame(columns=["Date","Ticker","sentiment_raw","sentiment_z"]).to_csv(Path(args.outdir)/"sentiment.csv", index=False)
        pd.DataFrame(columns=["source","title","desc","link","published"]).to_csv(Path(args.outdir)/"news_articles.csv", index=False)
        print("news: empty"); return
    df["text"] = (df["title"].astype(str).fillna("") + " " + df["desc"].astype(str).fillna("")).str.strip()
    df = df.drop_duplicates(subset=["link"]).reset_index(drop=True)
    df["sentiment"] = df["text"].apply(sentiment)
    today = pd.Timestamp.utcnow().tz_localize(None).normalize()
    s_raw = float(df["sentiment"].mean()) if len(df) else 0.0
    out = pd.DataFrame([{"Date":today, "Ticker":t, "sentiment_raw":s_raw} for t in uni["Ticker"].unique().tolist()])
    grp = out.groupby("Date")["sentiment_raw"]
    out["sentiment_z"] = grp.transform(lambda s:(s-s.mean())/(s.std(ddof=0)+1e-12))
    out.to_csv(Path(args.outdir)/"sentiment.csv", index=False)
    df[["source","title","desc","link","published"]].to_csv(Path(args.outdir)/"news_articles.csv", index=False)
    print("news: wrote sentiment.csv + news_articles.csv")
if __name__ == "__main__": main()
