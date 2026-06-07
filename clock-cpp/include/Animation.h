#pragma once

#include <algorithm>
#include <array>
#include <string>
#include <vector>
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

namespace render {
    inline int frameWidth = 0;
    inline int frameHeight = 0;
    inline std::vector<std::array<int, 3>> framePixels;

    inline void BeginFrame(int width, int height) {
        frameWidth = width;
        frameHeight = height;
        framePixels.assign(width * height, {0, 0, 0});
    }

    inline int Index(int x, int y) {
        if (x < 0 || x >= frameWidth || y < 0 || y >= frameHeight) return -1;
        return y * frameWidth + x;
    }

    inline void SetPixel(rgb_matrix::FrameCanvas* canvas, int x, int y, int r, int g, int b) {
        int idx = Index(x, y);
        if (idx < 0) return;
        std::array<int, 3> color = {
            std::max(0, std::min(255, r)),
            std::max(0, std::min(255, g)),
            std::max(0, std::min(255, b)),
        };
        framePixels[idx] = color;
        canvas->SetPixel(x, y, color[0], color[1], color[2]);
    }

    inline std::array<int, 3> GetPixel(int x, int y) {
        int idx = Index(x, y);
        if (idx < 0 || idx >= static_cast<int>(framePixels.size())) return {0, 0, 0};
        return framePixels[idx];
    }

    inline void BlendPixel(rgb_matrix::FrameCanvas* canvas, int x, int y,
                           int r, int g, int b, float alpha) {
        int idx = Index(x, y);
        if (idx < 0) return;
        float a = std::max(0.0f, std::min(1.0f, alpha));
        if (a <= 0.0f) return;
        if (a >= 1.0f) {
            SetPixel(canvas, x, y, r, g, b);
            return;
        }
        auto base = framePixels[idx];
        SetPixel(canvas, x, y,
            int(base[0] * (1.0f - a) + r * a),
            int(base[1] * (1.0f - a) + g * a),
            int(base[2] * (1.0f - a) + b * a));
    }

    inline void AddPixel(rgb_matrix::FrameCanvas* canvas, int x, int y,
                         int r, int g, int b, float alpha = 1.0f) {
        int idx = Index(x, y);
        if (idx < 0) return;
        float a = std::max(0.0f, std::min(1.0f, alpha));
        if (a <= 0.0f) return;
        auto base = framePixels[idx];
        SetPixel(canvas, x, y,
            std::min(255, int(base[0] + r * a)),
            std::min(255, int(base[1] + g * a)),
            std::min(255, int(base[2] + b * a)));
    }
}
