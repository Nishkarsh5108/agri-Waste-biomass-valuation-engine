# Multi Spectral Data Ingestion:

we can use Google Earth Engine (GEE python API) : we give the coordinates of the agricultural belts and it gives us NDVI

> NDVI: normalised difference vegetation index, NIR: near infrared

$$
NDVI = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}
$$

when crop is growing NDVI goes upto 1 and it sinks to 0 when no crop is growing (farmer has harvested it), so we can plot a graph of timeline of NDVI of the land and it will give us the harvesting dates.

#### Automation pipeline:

* filter out clouds from sattelite images using a `QA60` band in Sentinel-2.
* python script using geemap or ee library which pings GEE every 3-5 days (sentinel 2's revisit time)
* we dont need to save images, extract the average NDVI values along with the date for the farm polygon and save it to a database.

#### Prediction model:

feed that historical NDVI curve into a LSTM or XGboost pipeline which predicts when will the NDVI will hit "harvested" threshold.

#### Agricultural Belts:

for geting the agricultural belts automatically we need the region polygons to feed into GEE, so we will use India's open sourced dataset for the region polygons districtwise in the GeoJSON format, since stubble burning is more prominant in the north india, we will focus on the two major states : Punjab and Haryana.





we can estimate the final price of the stubble on farmer's device using the density genreated by Manya's CV model, and use satellite data (NDVI) to roughly estimate the stubble health, to produce final density
we would ask the farmer for land area
then the app would give an estimate amount of money the farmer would get

the final amount which farmer gets would be calculated by the factory where it would be processed
