#!/bin/bash
if [ -z "${PIXIEDUST_EGG}" ]; then
    echo installing pixiedust from PYPI
    pip install --upgrade pixiedust
else
    echo install pixiedust from ${PIXIEDUST_EGG}
    pip install --exists-action=w ${PIXIEDUST_EGG}
fi

if [ -z "${PIXIEGATEWAY_EGG}" ]; then
    echo installing pixiegatewayfrom PYPI
    pip install --upgrade pixiegateway
else
    echo install pixiegateway from ${PIXIEGATEWAY_EGG}
    pip install --exists-action=w ${PIXIEGATEWAY_EGG}
fi

jupyter pixiegateway --ip 0.0.0.0 --port 8888
