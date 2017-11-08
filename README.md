# PixieGateway

PixieGateway allows [PixieDust](https://github.com/ibm-watson-data-lab/pixiedust) users to free their apps and charts from the confines of data science notebooks, in order to better share their work.

PixieGateway is a web application server used for sharing charts and running PixieApps as web applications. With PixieDust and PixieGateway, developers and data scientists can more easily make the analytics in their notebooks available to people who are less comfortable with Jupyter Notebooks.

![A PixieDust chart, published as a webpage using PixieGateway.](https://ibm-watson-data-lab.github.io/pixiedust/_images/pixiegateway-published-chart.png)

From a PixieDust chart or PixieApp in a Jupyter Notebook, publishing your work via PixieGateway is as simple as clicking a button and providing the PixieGateway server location. After that, your analytics are only a URL away.

## Local Install

Install the pixiegateway package from PyPi. On the command line, run the following (Note: PixieGateway supports both Python 2.7 and 3.x):

```
pip install pixiegateway
```

Start the PixieGateway with a simple command:

```
jupyter pixiegateway --port <portnumber>
```

Example output:

```
dtaieb$ jupyter pixiegateway --port 8899
[PixieGatewayApp] Kernel started: b5be0b3b-a018–4ace-95d1-d94b556a0bfe
kernel client initialized
[PixieGatewayApp] Jupyter Kernel Gateway at http://127.0.0.1:8899
```

Go to `http://localhost:<portnumber>/pixieapps` to review and use your apps.

See the PixieDust docs for instructions on deploying a PixieGateway server to the cloud.

## Documentation

Because of its dependency on the PixieDust project, PixieGateway documentation is included as part of the [PixieDust docs site](https://ibm-watson-data-lab.github.io/pixiedust/pixiegateway.html).

Additionally, these blog articles provide more context on the development and uage of [PixieApp web publishing](https://medium.com/ibm-watson-data-lab/deploy-your-analytics-as-web-apps-using-pixiedusts-1-1-release-d08067584a14) and [PixieDust chart sharing](https://medium.com/ibm-watson-data-lab/share-your-jupyter-notebook-charts-on-the-web-43e190df4adb).

## License

**Apache License, Version 2.0**. 

For details and all the legalese, [read LICENSE](https://github.com/ibm-watson-data-lab/pixiegateway/blob/master/LICENSE).


