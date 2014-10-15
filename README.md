IEEE2015
========

This is the code for the University of Florida's 2015 IEEE Robot.
You need Ubuntu 14.04, and ROS Indigo. For some installation instructions, see github.com/uf-mil/getting_started

## Getting started

All of this is written for Ubuntu 14.04 (Trusty Tahr) and ROS Indigo (ros.org/install)

A good linux tutorial is [here](http://info.ee.surrey.ac.uk/Teaching/Unix/)

Once you make your catkin workspace (the ROS tutorials will teach you how to do this), go to the src folder, and clone this repository
```cd ~/catkin_ws/src
git clone git@github.com:ufieeehw/IEEE2015.git```

Your directory structure should like like "... /catkin_ws/src/IEEE2015/ros/"


### Simulators
To use the 2D Simulators/Visualizers, you need pygame
```sudo apt-get install pygame```

If you want to use the simulator, you need some Gazebo packages

```sudo apt-get install ros-indigo-gazebo-ros-pkgs ros-indigo-ros-control ros-indigo-ros-controllers```

### Install Pre-Requisites

To get everything without any effort, do:
```sudo apt-get install pygame ros-indigo-gazebo-ros-pkgs ros-indigo-ros-control ros-indigo-ros-controllers```

then run 
```catkin_make -C ~/catkin_ws```


## **Git Best Practices**

* When you commit something, the message should be of format "TOPIC: Verb action" - ex: "VISION: Add etch-a-sketch detection". This is important so that we can see a chronological list of commits and know what has caused changes

* Please include a readme.md with any new package. It should describe:
    * The topics it publishes to and listens to
    * A brief explanation of what the package does

* Commit ROS-ready code to the ROS directory under the appropriate package

* Commit non-ROS-ready code to the python, XMega or cpp directory as appropriate

* Only commit non-text files (Like pictures, 3D models, etc) if they are necessary to run or test your code!

* Commit everything, even if it's unfinished! The value of git is being able to track progress and see your code history

Th-th-th-that's all folks!


## Coding Practices

* Simplicity is more important than speed

* Reliability and accuracy are more important than speed

* Uncommented code is as good as an empty file

* Use the metric units! Don't use imperial! No imperial!

* When publishing and subscribing to measured topics, ALWAYS SPECIFY UNITS AND A REFERENCE FRAME!

* Indent with 4 spaces

