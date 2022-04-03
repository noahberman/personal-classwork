#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 11 14:45:20 2022

@author: noah
"""

import pandas as pd
from sodapy import Socrata
import os 
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import geopandas
import numpy as np

PATH = '/Users/noah/Documents/GitHub/personal-classwork-samples/Wind Plotting Sample'

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
def shapefile_reader(PATH, fname, shape_name, statefp='17'):
    shape = os.path.join(PATH, fname)
    geo_shape = geopandas.read_file(shape)
    geo_shape.columns = geo_shape.columns.str.lower()
    final_shape = geo_shape[geo_shape['name']==shape_name]     
    if 'statefp' in geo_shape.columns:
        final_shape = final_shape[final_shape['statefp']==statefp]
    return final_shape

# retrieving CCAO data
def ccao_retriever(API, columns, limit=1869232, year=2014, where='class == 100'):
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

def plot_one(cook, ccao, nrel, chicago):
    chicago.to_crs('EPSG:4326', inplace=True)
    nrel.set_crs('EPSG:4326', inplace=True)
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


nrel_gdf = nrel_concatenator()
lake_michigan = shapefile_reader(PATH, 'Boundaries - Lake Michigan/ne_10m_lakes.shp', 'Lake Michigan')
df_cook = shapefile_reader(PATH, 'Boundaries - Cook/cb_2018_us_county_20m.shp', 'Cook')
df_chicago = shapefile_reader(PATH, 'Boundaries - City/geo_export_7a96e0b9-b9f7-49d7-b280-f703b910b99f.shp', 'CHICAGO')
results_df = ccao_retriever('tnes-dgyi', 'pin, year, class')
loc_df = ccao_retriever('c49d-89sn', 'pin, mailing_zip, longitude, latitude')
ccao_gdf = ccao_merger() # this takes a moment to run
wind_df = wind_merger() # this takes a moment to run
plot_one(df_cook, ccao_gdf, nrel_gdf, df_chicago)
