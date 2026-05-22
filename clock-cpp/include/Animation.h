#pragma once

#include <string>
#include <led-matrix.h>

// Abstract base for all animation plugins.
//
// Concrete subclasses live in src/animations/. The plugin interface mirrors
// the Python Animation class: name(), conditions(), themes(), layer(),
// persistent() are class-level properties; update() and draw() are called
// once per frame; isDone() signals the scheduler to retire the instance.
//
// Layer values (draw order, low → high):
//   "background"  – sky gradient / star field
//   "celestial"   – sun, moon, shooting stars
//   "clouds"      – cloud bodies + precipitation
//   "foreground"  – overlays drawn on top (firefly, butterflies, etc.)

class Animation {
public:
    virtual ~Animation() = default;

    // Advance internal state by one frame.
    virtual void update() = 0;

    // Render to the double-buffer canvas.
    virtual void draw(rgb_matrix::FrameCanvas* canvas) = 0;

    // True when the animation has completed and should be retired.
    virtual bool isDone() const = 0;

    // Plugin metadata — must match the Python class attributes.
    virtual const std::string& name()       const = 0;
    virtual const std::string& layer()      const = 0;
    virtual bool               persistent() const = 0;
};
