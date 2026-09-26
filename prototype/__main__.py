import argparse
import os


def main():
    parser = argparse.ArgumentParser(description="Start CiteFrontier Live")
    parser.add_argument("--backend", choices=["lightweight", "dense"], default="lightweight")
    parser.add_argument("--parser", choices=["rules", "spacy", "bert", "shadow", "auto"], default="spacy")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    os.environ["CITEFRONTIER_BACKEND"] = args.backend
    os.environ["CITEFRONTIER_PARSER"] = args.parser
    import uvicorn
    uvicorn.run("prototype.server:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
