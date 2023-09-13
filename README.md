## Tools to read QTVR 1 files


Example files can be downloaded from:
https://www.dr-lex.be/info-stuff/qtvr.html

PRs welcome

## Build

A special build for PyAV is needed with 2 PRs combined.
    https://github.com/PyAV-Org/PyAV/pull/1145
    https://github.com/PyAV-Org/PyAV/pull/1163


To build PyAV:
    ```
    git clone https://github.com/rvanlaar/PyAV
    cd PyAV
    git switch cython3
    source scripts/activate.sh
    scripts/build-deps
    python3 setup.pt bdist_wheel
    ```

This will create a file in dist/. In my case `av-10.0.0-cp310-cp310-linux_x86_64.whl`

Add PyAV with poetry:
    ```
    poetry add ../PyAV/dist/av-10.0.0-cp310-cp310-linux_x86_64.whl
    ```
