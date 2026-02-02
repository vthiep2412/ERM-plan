
import sys
import os

# Add current directory to sys.path to find 'target' package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from target.agent import main

if __name__ == "__main__":
    main()
