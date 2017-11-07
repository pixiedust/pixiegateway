#!/bin/bash
if [ -z "${PIXIEGATEWAY_EGG}" ]; then
    echo installing from PYPI
    pip install --upgrade pixiegateway
else
    echo install from ${PIXIEGATEWAY_EGG}
    pip install --exists-action=w -e ${PIXIEGATEWAY_EGG}
fi    

jupyter pixiegateway --ip 0.0.0.0 --port 8888
