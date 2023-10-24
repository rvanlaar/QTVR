## Tools to read QTVR 1 files


Example files can be downloaded from:
https://www.dr-lex.be/info-stuff/qtvr.html

PRs welcome

## Build

Step 1: install poetry:

    https://python-poetry.org/docs/#installation

Step 2: run `poetry install`
Step 3: run `poetry shell`

A special build for PyAV is needed with 2 PRs combined.
    https://github.com/PyAV-Org/PyAV/pull/1145
    https://github.com/PyAV-Org/PyAV/pull/1163


To build PyAV:
    ```
    git clone https://github.com/rvanlaar/PyAV -b bits_per_coded_sample
    cd PyAV
    source scripts/activate.sh
    scripts/build-deps
    python3 setup.py bdist_wheel
    
    # fix wheel libs

    pip install auditwheel
    sudo apt install patchelf

    LD_LIBRARY_PATH=.vendor/build/ffmpeg-6.0:$LD_LIBRARY_PATH auditwheel repair --plat linux_x86_64 -w output-dir dist/*whl
    ```

This will create a file in output-dir/. In my case `pyav-11.2.0-cp311-cp311-linux_x86_64.whl`

Add PyAV with poetry:
    ```
    poetry add ../PyAV/dist/av-10.0.0-cp310-cp310-linux_x86_64.whl
    ```

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
