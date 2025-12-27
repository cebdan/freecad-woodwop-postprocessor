#!/bin/bash
# Script to clone FreeCAD repository

echo "Cloning FreeCAD repository..."
cd ~/Documents

# Check if FreeCAD directory already exists
if [ -d "FreeCAD" ]; then
    echo "FreeCAD directory already exists."
    read -p "Do you want to remove it and clone fresh? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf FreeCAD
        echo "Removed existing FreeCAD directory."
    else
        echo "Using existing FreeCAD directory."
        cd FreeCAD
        git pull
        exit 0
    fi
fi

# Clone FreeCAD repository
git clone https://github.com/FreeCAD/FreeCAD.git

if [ $? -eq 0 ]; then
    echo "✓ FreeCAD cloned successfully!"
    echo ""
    echo "Repository location: ~/Documents/FreeCAD"
    echo ""
    echo "Useful commands:"
    echo "  cd ~/Documents/FreeCAD"
    echo "  find src/Mod/Path -name '*.py' | grep -i g41"
    echo "  grep -r 'G41\\|G42' src/Mod/Path/"
else
    echo "✗ Failed to clone FreeCAD repository"
    exit 1
fi

