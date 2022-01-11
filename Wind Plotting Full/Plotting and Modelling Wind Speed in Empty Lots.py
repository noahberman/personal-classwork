#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Nov 28 18:28:29 2021

@author: noah and justin
"""

import pandas as pd
from sodapy import Socrata
import os 
import sys
import requests
import matplotlib.pyplot as plt
import matplotlib.colors
import matplotlib.patches as mpatches
import geopandas
import folium
from folium.features import DivIcon
import geojson
from shapely.ops import nearest_points
import numpy as np
from sympy import Point, Polygon
import statsmodels.api as sm



PATH = '/Users/noah/Documents/GitHub/final-project-noah-berman-s-team/'
#PATH_NREL = os.path.join(PATH,'Wind Data (Emailed from NREL)')

# Retrieving weather station coordinate information
def nrel_concatenator(PATH=os.path.join(PATH,'Wind Data (Emailed from NREL)')):
    lon = []
    lat = []
    for file in os.listdir(PATH):    
        # reading content into data frame
        df = pd.read_csv(os.path.join(PATH, file))
        lon.append([df.columns[-3]])
        lat.append([df.columns[-1]])
    lon = [item for sublist in lon for item in sublist] # flatten the list
    lon = [float(i) for i in lon] # convert to float
    lat = [item for sublist in lat for item in sublist]
    lat = [float(i) for i in lat]
    sites_df = pd.DataFrame({'Latitude': lat,'Longitude': lon})
    gdf = geopandas.GeoDataFrame(
        sites_df, geometry=geopandas.points_from_xy(sites_df.Longitude, sites_df.Latitude))
    return gdf

# Read in shapefiles  
# Sources: 
# Lake Michigan - http://www.naturalearthdata.com/downloads/10m-physical-vectors/
# Cook County - https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.html
# Chicago - https://github.com/ChicagoCityscape/pins
def shapefile_reader(PATH, fname, shape_name, statefp='17'):
    shape = os.path.join(PATH, fname)
    geo_shape = geopandas.read_file(shape)
    geo_shape.columns = geo_shape.columns.str.lower()
    final_shape = geo_shape[geo_shape['name']==shape_name]     
    if 'statefp' in geo_shape.columns:
        final_shape = final_shape[final_shape['statefp']==statefp]
    return final_shape

# retrieving CCAO data
def ccao_retreiver(API, columns, limit=1869232, year=2014, where='class == 100'):
    client = Socrata('datacatalog.cookcountyil.gov', None)
    if API == 'tnes-dgyi':
        results = client.get(API, year=year, select=columns, limit=limit, where=where)
    else:
        results = client.get(API, select=columns, limit=limit)
    results_df = pd.DataFrame.from_records(results)
    if 'pin' in results_df.columns:
        results_df['pin'] = results_df['pin'].str.replace(r'\-', '')
    return results_df    

# Merging CCAO data
def ccao_merger():
    full_ccao = pd.merge(results_df, loc_df, on='pin', how='left')
    full_ccao = full_ccao.dropna()
    ccao_gdf = geopandas.GeoDataFrame(
        full_ccao, geometry=geopandas.points_from_xy(full_ccao.longitude, full_ccao.latitude))
    return ccao_gdf

# check distribution of weather sites
def check_weather_sites():
    fig, ax = plt.subplots(figsize=(10,10))
    ax = df_cook.plot(ax=ax, color='white', edgecolor='black')
    ax = nrel_gdf.plot(ax = ax, color='red')
    plt.savefig(os.path.join(PATH, 'checking observation sites.png'))

# Find nearest NREL station to each of these points
# https://towardsdatascience.com/nearest-neighbour-analysis-with-geospatial-data-7bcd95f34c0e 
def calc_closest(row, destination, val, col='geometry'):
    dest_unary = destination['geometry'].unary_union
    nearest_geom = nearest_points(row[col], dest_unary)
    match_geom = destination.loc[destination.geometry == nearest_geom[1]]
    match_value = match_geom[val].to_numpy()[0]
    return match_value

# Get the nearest geometry, apologies that this takes several minutes to run. Like a good long time.
# Then get the distance from station to lake in km.
def get_dist_col(from_gdf, to_gdf):
    to_gdf.set_crs(epsg=4326, inplace=True)
    from_gdf['nearest_geom'] = from_gdf.apply(calc_closest, destination=to_gdf, val='geometry', axis=1)
    return from_gdf

# building full NREL df:
def wind_merger(PATH=os.path.join(PATH,'Wind Data (Emailed from NREL)')):
    df_list = []
    for file in os.listdir(PATH):    
        df = pd.read_csv(os.path.join(PATH, file))
        lat = df.columns[-1]
        lon = df.columns[-3]
        df.drop(df.columns[[-1,-3]],axis=1,inplace=True)
        df.columns = df.iloc[0]
        df = df.drop(labels=0, axis=0)
        df = df.apply(pd.to_numeric)
        df = df.groupby(['Year', 'Month'], as_index=False)['wind speed at 80m (m/s)'].mean()
        df['Latitude'] = lat
        df['Longitude'] = lon
        df_list.append(df)
    final_content = pd.concat(df_list)
    return final_content

# merging CCAO and NREL:
def clean_merge_wind_ccao(wind_df, ccao_gdf, lake_michigan):
    wind_df['Good Weather'] = np.where(wind_df['wind speed at 80m (m/s)'] > 6.7, 1, 0)
    ccao_gdf['nearest_geom_lon'] = ccao_gdf.nearest_geom.apply(lambda p: p.x).astype(float).round(7)
    ccao_gdf['nearest_geom_lat'] = ccao_gdf.nearest_geom.apply(lambda p: p.y).astype(float).round(7)
    wind_gdf = geopandas.GeoDataFrame(
        wind_df, geometry=geopandas.points_from_xy(wind_df.Longitude, wind_df.Latitude))
    wind_gdf['Longitude'] = wind_gdf.Longitude.astype(float)
    wind_gdf['Latitude'] = wind_gdf.Latitude.astype(float)
    wind_gdf = wind_gdf.set_crs('EPSG:4326')
    wind_gdf.to_crs(epsg=3857, inplace=True)
    lake_michigan.to_crs(epsg=3857, inplace=True)
    wind_gdf['distance_to_lake'] = wind_gdf.geometry.apply(lambda x: lake_michigan.distance(x).min()) 
    wind_gdf['distance_to_lake'] = wind_gdf['distance_to_lake'] / 1000
    wind_gdf = wind_gdf.round(7)
    complete_gdf = pd.merge(ccao_gdf, wind_gdf, how='left',right_on=['Latitude', 'Longitude'],
                            left_on=['nearest_geom_lat', 'nearest_geom_lon'])
    return complete_gdf

# exporting files needed for interactive map
def export_for_jupyter(gdf, cook_file):
    gdf = gdf.set_geometry('geometry_x')
    gdf.loc[gdf['Good Weather'] == 1, 'Good Weather'] = 'Over 6.7 m/s'
    gdf.loc[gdf['Good Weather'] == 0, 'Good Weather'] = 'Under 6.7 m/s'
    gdf['Month'].astype(str).astype(int)
    gdf.crs = 'EPSG:4326'
    exprt_gdf = gdf[['geometry_x', 'Month', 'Good Weather']]
    exprt_gdf.to_file(os.path.join(PATH, 'complete data.shp'))
    cook_file.to_file(os.path.join(PATH, 'cook.shp'))

# Mapping all data
def plot_one(cook, ccao, nrel, chicago):
    chicago.to_crs('EPSG:4326', inplace=True)
    nrel.to_crs('EPSG:4326', inplace=True)
    cook.to_crs('EPSG:4326', inplace=True)
    fig, ax = plt.subplots(figsize=(10,10)) # maybe this is just of interest, not worth keeping
    ax = cook.plot(ax=ax,figsize=(10, 6))
    ax = ccao.plot(ax=ax, marker='o', color='white', markersize=.005)
    ax = nrel.plot(ax=ax, color='darkorange', markersize=2)
    ax = chicago.plot(ax=ax, edgecolor='black', linestyle='dashed', facecolor='none')
    style = dict(size=15, color='black')
    ax.text(-87.5, 41.9, 'Chicago', ha='right', **style)
    ax.set_title('Distribution of Vacant Lots \n and NREL Weather Stations in Cook County', fontsize=20)
    ax.set_axis_off()
    fig.patch.set_facecolor('ivory')
    vacant_patch = mpatches.Patch(facecolor='white', edgecolor='black', label='Vacant Lots')
    nrel_patch = mpatches.Patch(color='darkorange', label='Weather Stations')
    ax.legend(handles=[vacant_patch, nrel_patch], loc='upper right')
    fig.savefig(os.path.join(PATH,'lots and stations dist.png'), dpi=600)

# Fitting the model https://www.geeksforgeeks.org/ordinary-least-squares-ols-using-statsmodels/
def model_the_data(gdf, windspeed=6.5):
    model_data = gdf.groupby(['pin', 'longitude', 'latitude']).mean().reset_index()
    model_data['Good Weather'] = np.where(model_data['wind speed at 80m (m/s)'] > windspeed, 1, 0)    
    x = model_data['distance_to_lake'].tolist()
    y = model_data['Good Weather'].tolist()
    x = sm.add_constant(x)
    result = sm.OLS(y, x).fit()
    print(result.summary())
    return model_data


nrel_gdf = nrel_concatenator()
lake_michigan = shapefile_reader(PATH, 'ne_10m_lakes.shp', 'Lake Michigan')
df_cook = shapefile_reader(PATH, 'cb_2018_us_county_20m.shp', 'Cook')
df_chicago = shapefile_reader(PATH, 'Boundaries - City/geo_export_7a96e0b9-b9f7-49d7-b280-f703b910b99f.shp', 'CHICAGO')
results_df = ccao_retreiver('tnes-dgyi', 'pin, year, class')
loc_df = ccao_retreiver('c49d-89sn', 'pin, mailing_zip, longitude, latitude')
ccao_gdf = ccao_merger()
ccao_gdf = get_dist_col(ccao_gdf, nrel_gdf) # the problem is here
check_weather_sites()
wind_df = wind_merger()
full_gdf = clean_merge_wind_ccao(wind_df, ccao_gdf, lake_michigan)
plot_one(df_cook, ccao_gdf, nrel_gdf, df_chicago)
model_data = model_the_data(full_gdf, windspeed=6.5)
export_for_jupyter(full_gdf, df_cook)
