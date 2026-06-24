# MoClo Backbone Feature - User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Managing Backbones](#managing-backbones)
4. [Checking Compatibility](#checking-compatibility)
5. [Assembling Plasmids](#assembling-plasmids)
6. [Exporting Results](#exporting-results)
7. [Tips and Best Practices](#tips-and-best-practices)
8. [Troubleshooting](#troubleshooting)

## Introduction

### What is the MoClo Backbone Feature?

The MoClo (Modular Cloning) Backbone Feature allows you to:
- Upload and manage MoClo-compatible backbone vectors
- Check which cassettes are compatible with your backbones
- Assemble cassettes into backbones to create final plasmids
- Export assembled plasmids in multiple formats

### What is MoClo?

MoClo is a modular cloning system that uses Type IIS restriction enzymes (like BsaI) to assemble DNA parts. The system relies on:
- **Backbones**: Acceptor vectors with restriction sites that define insertion points
- **Cassettes**: Pre-assembled DNA parts with compatible overhangs
- **Golden Gate Assembly**: One-pot reaction that cuts and ligates DNA parts

### Key Concepts

**Overhangs**: 4-base sequences exposed after restriction enzyme digestion. For successful assembly, cassette overhangs must match backbone slot overhangs.

**Slots**: Insertion sites in a backbone where cassettes can be inserted. Backbones can have one or multiple slots.

**Compatibility Score**: A percentage (0-100%) indicating how well a cassette matches a backbone's requirements.

## Getting Started

### Prerequisites

1. **Account**: You need to be logged in to use this feature
2. **Cassettes**: Create cassettes first using the Assembly page
3. **Backbone Files**: Obtain GenBank (.gb) files for your MoClo backbones

### Supported File Formats

- **GenBank (.gb, .gbk)**: Standard format for sequence files with annotations
- Must contain valid DNA sequence
- Should include restriction site annotations (optional but helpful)

## Managing Backbones

### Uploading a Backbone

1. **Navigate to Backbones Page**
   - Click "Backbones" in the main navigation

2. **Click "Upload Backbone"**
   - A form will appear

3. **Select GenBank File**
   - Click "Choose File" or drag-and-drop
   - Select your .gb file

4. **Enter Backbone Information**
   - **Name**: Give your backbone a descriptive name (e.g., "pYTK001")
   - **Description**: Optional details about the backbone

5. **Upload**
   - Click "Upload" button
   - Wait for processing (usually <5 seconds)
   - Success message will appear

### What Happens During Upload?

The system automatically:
1. Parses the GenBank file
2. Extracts the DNA sequence
3. Identifies restriction sites (BsaI, BpiI, BsmBI)
4. Determines cassette insertion slots
5. Calculates overhang sequences
6. Stores backbone in your library

### Viewing Backbone Details

1. **Click on a Backbone Card**
   - Opens detailed view in a modal

2. **Information Displayed**
   - Backbone name and description
   - Total length in base pairs
   - Number of cassette slots
   - Creation date
   - Restriction site positions
   - Overhang sequences for each slot
   - List of compatible cassettes

### Deleting a Backbone

1. **Click "Delete" Button** on backbone card
2. **Confirm Deletion** in the dialog
3. Backbone is permanently removed

⚠️ **Warning**: Deleting a backbone does not delete plasmids already assembled with it.

## Checking Compatibility

### From Backbone View

1. **Open Backbone Details**
   - Click on a backbone card

2. **Scroll to "Compatible Cassettes"**
   - Shows all cassettes that can be inserted into this backbone

3. **Review Compatibility Information**
   - Cassette name
   - Length
   - Overhangs (5' and 3')
   - Compatibility score
   - Slot assignment (for multi-slot backbones)

4. **Quick Assembly**
   - Click "Assemble" button next to any cassette
   - Jumps directly to assembly page with selections pre-filled

### From Cassette View

1. **Navigate to "My Cassettes"**
   - Click "My Cassettes" in navigation

2. **Open Cassette Details**
   - Click on a cassette card

3. **Scroll to "Compatible Backbones"**
   - Shows all backbones that can accept this cassette

4. **Compatibility Badges**
   - 🟢 **Green (80-100%)**: Highly compatible, recommended
   - 🟡 **Yellow (50-79%)**: Moderately compatible, may work
   - 🔴 **Red (0-49%)**: Low compatibility, not recommended

### Understanding Compatibility Scores

**100%**: Perfect match
- Overhangs match exactly
- Cassette fits in available slot
- No conflicts detected

**80-99%**: Good match
- Overhangs match
- Minor considerations (e.g., feature overlap)

**50-79%**: Acceptable match
- Overhangs compatible but not ideal
- May require validation

**0-49%**: Poor match
- Overhangs don't match well
- Assembly likely to fail

## Assembling Plasmids

### Step-by-Step Assembly Process

#### Step 1: Navigate to Assembly Page

Click "Plasmid Assembly" in the navigation or click "Assemble" from a compatibility view.

#### Step 2: Select Backbone

1. **Browse Available Backbones**
   - Left panel shows all your backbones
   - Displays name, length, and slot count

2. **Click to Select**
   - Selected backbone is highlighted
   - Compatible cassettes load automatically

#### Step 3: Select Cassettes

1. **Browse Compatible Cassettes**
   - Right panel shows cassettes compatible with selected backbone
   - Displays name, length, overhangs, and compatibility score

2. **Click to Add Cassettes**
   - Click once to add to assembly
   - Click again to remove
   - Selected cassettes are highlighted

3. **Slot Limits**
   - Can only select as many cassettes as backbone has slots
   - Warning shown if you try to exceed limit

#### Step 4: Review Assembly Preview

1. **Preview Panel Appears**
   - Shows below the selection panels
   - Displays assembly statistics

2. **Check Information**
   - Backbone name
   - Slot count (filled/total)
   - Expected plasmid size
   - Cassette assignments

3. **Slot Assignments**
   - Each slot shows assigned cassette
   - Displays cassette name and overhangs
   - Can remove cassettes from individual slots

#### Step 5: Simulate Assembly

1. **Click "Simulate Assembly"**
   - Validates the assembly before performing it
   - Takes 1-2 seconds

2. **Review Simulation Results**
   - ✅ **Success**: Assembly is valid, ready to proceed
   - ❌ **Error**: Assembly will fail, shows reason
   - ⚠️ **Warnings**: Assembly may work but has issues

3. **Simulation Information**
   - Expected plasmid length
   - Feature count
   - Any warnings or errors

#### Step 6: Assemble Plasmid

1. **Click "Assemble Plasmid"**
   - Only enabled after successful simulation

2. **Enter Plasmid Name**
   - Prompt appears asking for name
   - Choose a descriptive name (e.g., "GFP Expression Plasmid")

3. **Confirm Assembly**
   - Click OK to proceed
   - Assembly takes 2-5 seconds

4. **View Results**
   - Success modal shows plasmid details
   - Plasmid ID
   - Final size
   - Feature count

5. **Next Steps**
   - Click "View All Plasmids" to see your plasmid library
   - Click "Create Another" to assemble another plasmid

### Multi-Cassette Assembly

For backbones with multiple slots:

1. **Select Multiple Cassettes**
   - Add cassettes one at a time
   - Order matters for slot assignment

2. **Slot Assignment**
   - First selected cassette → Slot 1
   - Second selected cassette → Slot 2
   - And so on...

3. **Rearranging**
   - Remove cassettes and re-add in desired order
   - Or use "Remove" button on specific slots

4. **Validation**
   - Simulation checks all cassettes
   - Ensures overhangs match for all slots

### Resetting Assembly

Click "Reset" button to:
- Clear all selections
- Start over with new backbone/cassettes
- Does not delete any data

## Exporting Results

### Viewing Assembled Plasmids

1. **Navigate to Plasmids Page**
   - Click "Plasmids" in navigation

2. **Browse Your Plasmids**
   - Cards show plasmid name, size, features, date
   - Circular map preview (if available)

3. **Open Plasmid Details**
   - Click on a plasmid card
   - View complete information

### Export Formats

#### GenBank Format (.gb)

**Best for:**
- Importing into sequence editors (SnapGene, Benchling, etc.)
- Preserving all feature annotations
- Sharing with collaborators

**Contains:**
- Complete sequence
- All features with positions
- Feature annotations
- Metadata

**How to Export:**
1. Open plasmid details
2. Click "Export GenBank"
3. File downloads automatically

#### FASTA Format (.fasta)

**Best for:**
- Sequence analysis tools
- BLAST searches
- Simple sequence storage

**Contains:**
- DNA sequence only
- Header with plasmid name and length
- No feature annotations

**How to Export:**
1. Open plasmid details
2. Click "Export FASTA"
3. File downloads automatically

#### Image Format (.png)

**Best for:**
- Presentations
- Lab notebooks
- Quick visualization
- Sharing on social media

**Contains:**
- Circular plasmid map
- Color-coded features
- Feature labels
- Size markers

**How to Export:**
1. Open plasmid details
2. Click "Export Image"
3. PNG file downloads

### Deleting Plasmids

1. Click "Delete" button on plasmid card
2. Confirm deletion
3. Plasmid is permanently removed

⚠️ **Warning**: This action cannot be undone.

## Tips and Best Practices

### Backbone Management

✅ **DO:**
- Use descriptive names (include vector name and version)
- Add detailed descriptions (resistance markers, special features)
- Keep backbones organized by project or purpose
- Verify GenBank files before uploading

❌ **DON'T:**
- Upload non-MoClo backbones (won't have correct restriction sites)
- Use generic names like "backbone1", "test"
- Upload corrupted or incomplete GenBank files

### Compatibility Checking

✅ **DO:**
- Check compatibility before attempting assembly
- Pay attention to compatibility scores
- Review overhang sequences manually if score is low
- Consider biological function, not just compatibility

❌ **DON'T:**
- Ignore low compatibility scores
- Assume all "compatible" cassettes will work biologically
- Skip the simulation step

### Assembly

✅ **DO:**
- Always simulate before assembling
- Review warnings carefully
- Use descriptive plasmid names
- Document your assemblies (keep notes)
- Export immediately after assembly

❌ **DON'T:**
- Skip simulation (may waste time on failed assemblies)
- Ignore warnings (they indicate potential issues)
- Use vague names like "plasmid1"
- Forget to export your results

### File Management

✅ **DO:**
- Keep original GenBank files backed up
- Export plasmids in multiple formats
- Organize exports in project folders
- Version your plasmids (v1, v2, etc.)

❌ **DON'T:**
- Rely solely on web interface for storage
- Delete backbones still in use
- Lose track of which cassettes were used

## Troubleshooting

### Upload Issues

**Problem**: "Failed to parse GenBank file"
- **Solution**: Verify file is valid GenBank format, not corrupted

**Problem**: "No restriction sites found"
- **Solution**: Backbone may not be MoClo-compatible, check for BsaI/BpiI/BsmBI sites

**Problem**: "Upload failed"
- **Solution**: Check file size (<10MB), check internet connection, try again

### Compatibility Issues

**Problem**: "No compatible cassettes found"
- **Solution**: Create cassettes with matching overhangs, or upload different backbone

**Problem**: "Low compatibility score"
- **Solution**: Check overhang sequences, may need different cassette or backbone

**Problem**: "Compatibility list not loading"
- **Solution**: Refresh page, check that cassettes exist in your library

### Assembly Issues

**Problem**: "Simulation failed"
- **Solution**: Review error message, check overhang compatibility, verify cassette selection

**Problem**: "Assembly failed"
- **Solution**: Try simulation again, check for database issues, contact support

**Problem**: "Assemble button disabled"
- **Solution**: Run simulation first, ensure simulation succeeded

### Export Issues

**Problem**: "Export failed"
- **Solution**: Check browser download settings, try different format, refresh page

**Problem**: "Image export not available"
- **Solution**: Cairo library may not be installed (contact administrator)

**Problem**: "GenBank file won't open"
- **Solution**: Verify file downloaded completely, try different sequence viewer

### General Issues

**Problem**: "Page not loading"
- **Solution**: Refresh browser, clear cache, check internet connection

**Problem**: "Changes not saving"
- **Solution**: Ensure you're logged in, check session hasn't expired

**Problem**: "Can't see my backbones/plasmids"
- **Solution**: Verify you're logged in as correct user, check filters

## Getting Help

If you encounter issues not covered here:

1. **Check the Testing Guide**: `TESTING_GUIDE.md` has detailed test cases
2. **Review API Documentation**: `docs/API_DOCUMENTATION.md` for technical details
3. **Contact Support**: Provide detailed description of issue with screenshots
4. **Report Bugs**: Include steps to reproduce, expected vs actual behavior

## Glossary

**Backbone**: Acceptor vector with restriction sites for cassette insertion

**Cassette**: Pre-assembled DNA part with compatible overhangs

**Overhang**: 4-base sequence exposed after restriction enzyme digestion

**Slot**: Insertion site in a backbone where a cassette can be inserted

**Golden Gate Assembly**: One-pot cloning method using Type IIS restriction enzymes

**Type IIS Enzyme**: Restriction enzyme that cuts outside its recognition sequence (e.g., BsaI)

**Compatibility Score**: Percentage indicating how well a cassette matches a backbone

**GenBank**: Standard file format for DNA sequences with annotations

**FASTA**: Simple file format containing only DNA sequence

**Feature**: Annotated region of DNA (gene, promoter, terminator, etc.)

## Additional Resources

- [MoClo Toolkit Documentation](https://www.addgene.org/cloning/moclo/)
- [GenBank Format Specification](https://www.ncbi.nlm.nih.gov/Sitemap/samplerecord.html)
- [Golden Gate Assembly Protocol](https://www.neb.com/protocols/2018/10/02/golden-gate-assembly-protocol)

---

**Version**: 1.0  
**Last Updated**: January 2026  
**Feedback**: Please report issues or suggestions for improvement
