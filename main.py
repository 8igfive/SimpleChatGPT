import argparse
from src import PROGRAM_NAME
from src import OPENAI_API_TOKEN
from src import MODELS
from src import DUMP_DIR
from src.client import Client

def main():
    parser = argparse.ArgumentParser(PROGRAM_NAME)
    parser.add_argument("-k", "--api_key", type=str, default=OPENAI_API_TOKEN,
                        help="OpenAI API KEY.")
    parser.add_argument("-m", "--model", type=str, choices=MODELS, default=MODELS[0],
                        help="Model to use.")
    parser.add_argument("-r", "--retry", type=int, default=3, 
                        help="Max retry time when fail to get response from OpenAI.")
    parser.add_argument("-d", "--dump_dir", type=str, default=DUMP_DIR,
                        help="Directory to save context cache.")
    parser.add_argument("-c", "--cache_path", type=str, default=None, 
                        help="Path to load context path")

    args = parser.parse_args()

    client = Client(args.api_key, args.model, args.retry, args.dump_dir, args.cache_path)
    client.start()

if __name__ == "__main__":
    main()