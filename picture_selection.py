#!/bin/python
import os, stat
import subprocess
from pickle import FALSE, TRUE
import shutil
import numpy as np
import random
from datetime import datetime
from time import strftime
from time import gmtime
from shutil import copy2
from PIL import Image
import cv2
from libsvm import svmutil
from brisque import BRISQUE
from numpy.testing._private.utils import print_assert_equal

# Create a new sub directory
# Remove it already exists
def create_new_subdir(folder, sub_folder):
    path = folder+sub_folder
    if os.path.exists(path) :
        shutil.rmtree(folder+sub_folder, onerror=remove_readonly)
    os.mkdir(path)

# Function to ensure read-only Windows folder can be removed
def remove_readonly(fn, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
        fn(path)
    except Exception as exc:
        print("Skipped:", path, "because:\n", exc)

# Move files from source to target folder
def move_file(file, src_folder, tgt_folder):
    os.rename(src_folder+file, tgt_folder+'/'+file)

# Copy files from source to target folder
def copy_file(file, src_folder, tgt_folder):
    copy2(src_folder+file, tgt_folder+'/'+file) 

# Get picture taken metatag as date string and datetime
def get_picture_dt(path):
    img = Image.open(path)
    dt = img._getexif()[36867]
    dt_str = str(dt)
    d = dt_str[0:4]+dt_str[5:7]+dt_str[8:10]
    return d, dt

def get_picture_blur(path):
    image = cv2.imread(path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    fm = cv2.Laplacian(gray, cv2.CV_64F).var()
    if fm < blur_threshold:
        return 1
    else:
        return 0

# Get picture resolution
def get_picture_res(path):
    image = cv2.imread(path)
    hgt, wid = image.shape[:2]
    if (wid > hgt):
        is_portrait = 0
    else:
        is_portrait = 1
    res = (wid*hgt)
    return res, is_portrait

def get_brightness_score(path):
    infoDict = {}
    process = subprocess.Popen([exifToolPath,path],stdout=subprocess.PIPE, stderr=subprocess.STDOUT,universal_newlines=True) 
    for tag in process.stdout:
        line = tag.strip().split(':')
        infoDict[line[0].strip()] = line[-1].strip()
    if len(infoDict)>100:
        return round(float(infoDict['Brightness Value'])*float(infoDict['Light Value']),2)
    else:
        return 0

# Get picture score based on brisq scoring model
def get_picture_score(path):
    if test_mode == TRUE:
        return random.randint(0, 100) 
    else:
        return brisq.get_score(path)

# Get all pictures with date and datetime information sorted
# Ignore picture without picture taken metatag
def get_photos_with_dt(path):
    dir_entries = os.scandir(path)
    cnt_suc = 0
    cnt_err = 0
    file_dict = {}
    for entry in dir_entries:
        if entry.is_file():
            try:
                file_dict[entry.name] = get_picture_dt(entry.path)
                cnt_suc = cnt_suc+1
            except:
                cnt_err = cnt_err+1
    print(str(datetime.now())+" Log: "+str(cnt_err)+" photos have been eliminated due to missing metadata ("+str(str(cnt_suc))+" remaining)")
    file_dict_sorted = sorted(file_dict.items(), key=lambda x: (x[1][0],x[1][1]))
    return file_dict_sorted

# Filter pictures based on parameter agg_seconds
# e.g. take only one (first) picture from 30 second interval if agg_seconds = 30
def get_photos_time_filtered(file_dict, agg_seconds):
    prev = ''
    counter = 0
    file_dict_reduced = {}
    for f in file_dict:
        if (prev != '' and prev[1][0] == f[1][0]):
            curr_dt = datetime.strptime(f[1][1], '%Y:%m:%d %H:%M:%S')
            prev_dt = datetime.strptime(prev[1][1], '%Y:%m:%d %H:%M:%S')
            diff = curr_dt-prev_dt
            if (diff.total_seconds() > agg_seconds):
                file_dict_reduced[f[0]] = f[1][0]
                counter = counter+1
                prev = f
        else:
            file_dict_reduced[f[0]] = f[1][0]
            prev = f
            counter = counter+1
    print(str(datetime.now())+" Log: "+str(len(file_dict)-len(file_dict_reduced))+" photos have been eliminated using "+str(agg_seconds)+" seconds aggregation timeframe ("+str(len(file_dict_reduced))+" remaining)")
    return file_dict_reduced

# Filter out blurry pictures
def get_photos_blur_filtered(file_dict):
    counter = 0
    sum_time_per_picture = 0 
    dict_len = len(file_dict)
    file_dict_reduced = {}
    prev = datetime.now()
    if (test_mode == FALSE):
        for f in file_dict:
            blurry = get_picture_blur(folder+f)
            if (blurry == 0):
                file_dict_reduced[f] = file_dict[f]
            else:
                pass
            counter = counter+1
            cur_time_per_picture = (datetime.now() - prev).total_seconds()
            sum_time_per_picture = sum_time_per_picture + cur_time_per_picture
            avg_time_per_picture = sum_time_per_picture / counter
            time_remaining = round((dict_len - counter) * avg_time_per_picture,0)
            time_remaining_str = strftime("%H:%M:%S", gmtime(time_remaining))
            print(str(datetime.now())+" Log: Photo "+str(counter)+" of "+str(dict_len)+" checked for blur ("+str(round((counter/dict_len)*100,1))+"%, "+time_remaining_str+" remaining) / "+f)
            prev = datetime.now()
        print(str(datetime.now())+" Log: "+str(dict_len-len(file_dict_reduced))+" photos have been eliminated due to blur"+" ("+str(len(file_dict_reduced))+" remaining)")
        return file_dict_reduced   
    else: 
        return file_dict

# Get resolution and score for all pictures, sort by date, landscape over portrait, resolution, brightness/light, score and return picture list
def get_photos_with_score_res(file_dict, folder):
    file_dict_score = {}
    counter = 0
    sum_time_per_picture = 0 
    prev = datetime.now()
    dict_len = len(file_dict)
    for f in file_dict:
        res_info = get_picture_res(folder+f)
        res = 100000000-res_info[0]
        res_str = '%09d' %res
        score = get_picture_score(folder+f)
        score_str = '%03d' %score
        brightness = 1000-get_brightness_score(folder+f)
        brightness_str = '%03d' %round(brightness,0)
        file_dict_score[f] = file_dict[f]+"_"+str(res_info[1])+"_"+res_str+"_"+brightness_str+"_"+score_str
        counter = counter+1
        cur_time_per_picture = (datetime.now() - prev).total_seconds()
        sum_time_per_picture = sum_time_per_picture + cur_time_per_picture
        avg_time_per_picture = sum_time_per_picture / counter
        time_remaining = round((dict_len - counter) * avg_time_per_picture,0)
        time_remaining_str = strftime("%H:%M:%S", gmtime(time_remaining))
        print(str(datetime.now())+" Log: Photo "+str(counter)+" of "+str(dict_len)+" scored ("+str(round((counter/len(file_dict))*100,1))+"%, "+time_remaining_str+" remaining) / "+f+" "+file_dict[f]+"_"+str(res_info[1])+"_"+res_str+"_"+brightness_str+"_"+score_str)
        prev = datetime.now()
    file_dict_score_sorted = sorted(file_dict_score.items(), key=lambda x: (x[1]))
    #print("\n".join(map(str, file_dict_score_sorted)))
    return file_dict_score_sorted

# Get number of pictures per day
def get_num_photos_per_day(file_dict_sorted):
    prev = ''
    counter = 0
    photos_per_day = {}
    for f in file_dict_sorted:
        if (prev == f[1][0:8] or prev == ''):
            counter = counter + 1
        else: 
            photos_per_day[prev] = counter
            counter = 1
        prev = f[1][0:8]
    photos_per_day[prev] = counter
    return photos_per_day

# Select pictures based on desired number of pictures in result set
def select_photos(photos_with_info, num_photos_per_date, min_no_photos, pct, folder, sub_folder):
    prev = ''
    cnt_logic = 0
    cnt_select = 0
    for p in photos_with_info:
        if (prev == p[1][0:8]):
            if (cnt_logic < max(round(num_photos_per_date[p[1][0:8]]*pct,0),min_no_photos)):
                #print(str(p[1][0:8])+" "+p[0])
                copy_file(p[0], folder, folder+sub_folder)
                cnt_select = cnt_select+1
            cnt_logic = cnt_logic+1
        else:
            #print(str(p[1][0:8])+" "+p[0])
            copy_file(p[0], folder, folder+sub_folder)
            cnt_select = cnt_select+1
            cnt_logic = 1
        prev = p[1][0:8]
    print(str(datetime.now())+" Log: "+str(cnt_select)+" photos have been selected into subfolder")

def user_inp_folder():
    while True:
        try:
            folder = input("Enter folder with pictures to select from:")
            if(not os.path.isdir(folder)):
                raise ValueError
        except ValueError:
            print("This is not a valid folder. Please try again.")
            continue
        else:
            print("Folder exists")
            break
    return folder

def user_input_int(min, max, text):
    while True:
        try:
            num = int(input(text))
            if (num < min or num > max):
                raise ValueError
        except ValueError:
            print("This is not a valid number (allowed: "+str(min)+"-"+str(max)+"). Please try again.")
            continue
        else:
            print("Number accepted")
            break
    return num

### Parameters ###
exifToolPath = 'C:/Program Files/exiftool/exifTool.exe'
sub_folder = "selection"
test_mode = FALSE

### Default Parameters ###
blur_threshold = 100
folder = "c:/pics/"
num_photos_to_select = 200
agg_seconds = 60
min_no_photos = 1

### User input ### 
#folder = user_inp_folder()
#num_photos_to_select = user_input_int(1,500,"Enter the number of pictures you would like to select:")
#agg_seconds = user_input_int(0,600,"Enter an interval in seconds you do not want to have more than one picture from:")
#min_no_photos = user_input_int(0,10,"Enter how many pictures you would like to have from each day:")

### Initialize brisque scoring model ###
brisq = BRISQUE()

### Create a new sub directory for pictures selected
create_new_subdir(folder, sub_folder)
### Get all pictures with date & datetime tag
photos_with_dt = get_photos_with_dt(folder)
### Get pictures filtered depending on time proximity
photos_filtered_time = get_photos_time_filtered(photos_with_dt, agg_seconds)
### Get picutres filtered on degree of blur
photos_filtered_blur = get_photos_blur_filtered(photos_filtered_time)
### Get resolution, brightness/light and scoring and sort pictures accordingly
photos_sorted = get_photos_with_score_res(photos_filtered_blur, folder)
### Get number pictures taken per day
num_photos_per_date = get_num_photos_per_day(photos_sorted)
### Derive percentage of pictures to be selected
pct = round((num_photos_to_select/len(photos_sorted)),2)
### Select pictures depending on quality and the percentage of pictures for selection
select_photos(photos_sorted, num_photos_per_date, min_no_photos, pct, folder, sub_folder)