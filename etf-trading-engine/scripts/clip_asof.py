import pandas as pd
import argparse

def main():
    parser = argparse.ArgumentParser(description="Clip EOD data up to an as-of date.")
    parser.add_argument("--input", required=True, help="Percorso del file di input (EOD completo).")
    parser.add_argument("--output", required=True, help="Percorso del file di output clippato.")
    parser.add_argument("--as-of", required=True, help="Data limite in formato YYYY-MM-DD.")
    parser.add_argument("--start", required=False, help="Data di inizio (opzionale).")
    args = parser.parse_args()

    df = pd.read_csv(args.input, parse_dates=["dt"])

    if args.start:
        df = df[(df["dt"] >= args.start) & (df["dt"] <= args.as_of)]
    else:
        df = df[df["dt"] <= args.as_of]

    df.to_csv(args.output, index=False)
    print(f"✅ Dati tagliati al {args.as_of} salvati in {args.output}")

if __name__ == "__main__":
    main()
