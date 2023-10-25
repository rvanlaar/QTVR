## Tools to read QTVR 1 files


Example files can be downloaded from:
https://www.dr-lex.be/info-stuff/qtvr.html

PRs welcome

## Build

Step 1: install poetry:

    https://python-poetry.org/docs/#installation

Step 2: run `poetry install`
Step 3: run `poetry shell`

## Usage

Running poetry install and poetry shell will install scripts in the virtual environment:

make_mosaic:
    Create a mosaic from object files, needs PyAV installed
    This version only uses ffmpeg via PyAV for the actual decoding of the frames.
    All other parsing is done with python.

make_mosaic_ffmpeg:
    Create a mosaic from object files, needs imagemagisk and ffmpeg
    This asks ffmpeg to just dump all images inside the quicktime movie
    and uses imagemagick to combine them into one mosaic

print_atoms:
    Prints all atoms from a quicktime file

decode_cinepak:
    Can read cinepak data and decode it. Module is fully in python
