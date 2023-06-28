#!/bin/bash

# wake up screen
# xset -display "$DISPLAY" dpms force on

echo "Setting up..."

# check that webcam is available
while [ ! -e /dev/video0 ] || [ ! -e /dev/video4 ]
do  
    if [ ! -e /dev/video0 ]
    then
        echo "- Webcam 1 not found, please make sure it is plugged in correctly..."
    fi
    if [ ! -e /dev/video4 ]
    then
        echo "- Webcam 2 not found, please make sure it is plugged in correctly..."
    fi
    sleep 2
done
echo "- Webcams set up."

# go to stylecam dir
cd ~/art_mirror/docker

# start a first time to enable the virtual webcam if it's not running
if [ -e /dev/video12 ]
then
    echo "- Virtual cam already loaded."
else
    echo "- Loading virtual cam..."
    docker-compose -f docker-compose-nvidia.yml run stylecam
    echo "- Virtual cam loaded."
fi

# start the program
echo ""
echo "Starting magic mirror..."

# start ffplay in the background to display the virtual cam output and save the PID
# -vf hflip mirrors the video horizontally, -vf "transpose=3" flips vertically and rotates 90 degrees
# -fs -video_size 1920x1080 displays the image fullscreen
ffplay -video_size 1008x504 -loglevel error /dev/video12 &
ffplay_pid=$!

# start the style-transfer
docker-compose -f docker-compose-nvidia.yml run stylecam

# kill ffplay if style-transfer finished
kill $ffplay_pid