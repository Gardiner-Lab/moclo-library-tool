# Image Export Implementation

## Overview

The image export functionality converts SVG visualizations of parts and cassettes into PNG format. This allows users to download and share visual representations of their genetic constructs.

## Implementation Details

### Core Functions

#### `svg_to_png(svg_content: str, output_width: Optional[int] = None) -> bytes`

Converts SVG content to PNG format using the cairosvg library.

**Parameters:**
- `svg_content`: SVG string to convert
- `output_width`: Optional width in pixels for the output PNG (scales proportionally)

**Returns:**
- PNG image data as bytes

**Raises:**
- `ValueError`: If SVG content is invalid or conversion fails

**Example:**
```python
svg = '<svg width="100" height="100">...</svg>'
png_data = svg_to_png(svg, output_width=200)
```

#### `generate_part_image(part: Part, width: int = 200) -> bytes`

Generates a PNG image representation of a single part.

**Features:**
- Colored rectangle based on part type
- Part name label
- Overhang sequences at both ends (5' and 3')
- Chevrons for Coding and Promoter types

**Parameters:**
- `part`: Part instance to visualize
- `width`: Width of the output image in pixels (default: 200)

**Returns:**
- PNG image data as bytes

#### `export_part_image(part_id: str, width: int = 200) -> Optional[bytes]`

Exports a part as a PNG image by part ID.

**Parameters:**
- `part_id`: ID of the part to export
- `width`: Width of the output image in pixels (default: 200)

**Returns:**
- PNG image data as bytes if part exists, None otherwise

#### `generate_cassette_image(cassette: Cassette, width: int = 800) -> bytes`

Generates a PNG image representation of a cassette.

**Features:**
- All component parts with their colors and types
- Part boundaries and labels
- Overhang sequences at junctions
- Compatibility indicators between parts (✓ for compatible, ✗ for incompatible)
- Chevrons for directional parts (Coding, Promoter)

**Parameters:**
- `cassette`: Cassette instance to visualize
- `width`: Width of the output image in pixels (default: 800)

**Returns:**
- PNG image data as bytes

**Raises:**
- `ValueError`: If cassette has no parts or image generation fails

#### `export_cassette_image(cassette_id: str, width: int = 800) -> Optional[bytes]`

Exports a cassette as a PNG image by cassette ID.

**Parameters:**
- `cassette_id`: ID of the cassette to export
- `width`: Width of the output image in pixels (default: 800)

**Returns:**
- PNG image data as bytes if cassette exists, None otherwise

## System Dependencies

The image export functionality requires the Cairo graphics library to be installed at the system level.

### Docker (Production)

Cairo dependencies are automatically installed in the Docker container via the Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y \
    gcc \
    libcairo2 \
    libcairo2-dev \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*
```

### Local Development

For local development, install Cairo system libraries:

**Ubuntu/Debian:**
```bash
sudo apt-get install libcairo2 libcairo2-dev libgdk-pixbuf2.0-0 libffi-dev
```

**macOS:**
```bash
brew install cairo
```

**Windows:**
Download and install GTK+ runtime from:
https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

## API Integration

The image export functionality is integrated into the REST API:

### Export Cassette as Image
```
GET /api/cassettes/:id/export/image
```

**Query Parameters:**
- `width` (optional): Width of the output image in pixels (default: 800)

**Response:**
- Content-Type: `image/png`
- Body: PNG image data

**Example:**
```bash
curl http://localhost:5000/api/cassettes/abc123/export/image?width=1200 > cassette.png
```

### Export Part as Image
```
GET /api/parts/:id/export/image
```

**Query Parameters:**
- `width` (optional): Width of the output image in pixels (default: 200)

**Response:**
- Content-Type: `image/png`
- Body: PNG image data

## Testing

### Unit Tests

Comprehensive unit tests are provided in `tests/test_export.py`:

- `test_svg_to_png_basic()` - Basic SVG to PNG conversion
- `test_svg_to_png_with_width()` - Conversion with custom width
- `test_svg_to_png_invalid_svg()` - Error handling for invalid SVG
- `test_generate_part_image_basic()` - Part image generation
- `test_generate_part_image_all_types()` - All part types
- `test_generate_cassette_image_basic()` - Cassette image generation
- `test_generate_cassette_image_multiple_parts()` - Multiple parts
- `test_cassette_image_with_incompatible_parts()` - Incompatible parts visualization
- And many more...

### Manual Testing

A manual test script is provided for testing in the Docker environment:

```bash
docker-compose exec web python test_image_export_manual.py
```

This script tests:
1. Basic SVG to PNG conversion
2. Part image generation
3. Cassette image generation

## Requirements Validation

This implementation satisfies the following requirements:

**Requirement 6.1**: Export cassettes as images
- ✓ Generates PNG images from cassettes

**Requirement 6.4**: Include part boundaries, types, and labels in images
- ✓ Part boundaries shown as separate rectangles
- ✓ Part types indicated by colors
- ✓ Part labels displayed on each part
- ✓ Overhang sequences shown at junctions
- ✓ Compatibility indicators between parts

**Requirement 6.5**: Export individual parts as images
- ✓ Generates PNG images from individual parts
- ✓ Includes part name, type, and overhangs

## Visual Design

### Part Colors
- **Coding**: Blue (#4A90E2)
- **NonCodingPromoter**: Green (#7ED321)
- **NonCodingTerminator**: Red (#D0021B)
- **NonCodingIntron**: Yellow (#F5A623)
- **NonCodingOther**: Gray (#9B9B9B)

### Directional Indicators
- Coding and Promoter parts display chevrons (>>>) to indicate 5' to 3' direction
- Other part types do not display chevrons

### Compatibility Indicators
- Green checkmark (✓) for compatible adjacent parts
- Red X (✗) with "Incompatible" label for incompatible adjacent parts

## Error Handling

The implementation includes robust error handling:

1. **Invalid SVG**: Raises `ValueError` with descriptive message
2. **Empty SVG**: Raises `ValueError`
3. **Cassette with no parts**: Raises `ValueError`
4. **Non-existent part/cassette**: Returns `None`
5. **Cairo library not found**: Raises `OSError` with installation instructions

## Performance Considerations

- PNG generation is relatively fast (< 100ms for typical cassettes)
- Image size scales with width parameter
- Default widths are optimized for web display:
  - Parts: 200px (suitable for thumbnails)
  - Cassettes: 800px (suitable for detailed view)
- Larger widths can be requested for high-resolution exports

## Future Enhancements

Potential improvements for future versions:

1. **Format Options**: Support for additional formats (JPEG, WebP)
2. **Custom Styling**: Allow users to customize colors and styles
3. **Annotations**: Add custom text annotations to images
4. **Batch Export**: Export multiple cassettes at once
5. **Vector Export**: Provide SVG download option for scalable graphics
6. **Image Metadata**: Embed cassette information in PNG metadata
