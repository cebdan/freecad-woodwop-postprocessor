# Changes Report: WoodWOP Post Processor Integration for FreeCAD

**Date:** 2025-12-27  
**Version:** 1.0

## Summary

Implemented integration of WoodWOP post-processor into FreeCAD with support for dual format output (MPR and NC) for comparison and MPR post-processor correction. Added automatic project report generation. Fixed file naming logic based on part name and Job.

## Modified Files

### 1. `/Users/user/Documents/freecad/.pixi/envs/default/Mod/CAM/Path/Post/scripts/woodwop_post.py`
**Source:** `/Users/user/Documents/freecad/src/Mod/CAM/Path/Post/scripts/woodwop_post.py`

#### Main Changes:

1. **Removed old direct file creation code**
   - Removed code block that created `.mpr`, `.nc`, and report files directly via `open()`
   - Removed `else:` block for stdout mode that also created files directly

2. **Changed return type of `export()` function**
   - **Before:** Function returned a string (G-code) or `True` (bool)
   - **After:** Function returns a list of tuples: `[("mpr", mpr_content), ("nc", gcode_content)]`
   - This allows FreeCAD to create separate files for each format

3. **Added return value validation**
   - Type checking for `mpr_content` and `gcode_content` (must be strings)
   - Type checking of result before return (must be a list)
   - Checking each list element (must be a tuple of 2 elements)
   - Final check for `bool` before return

4. **Added extensive logging**
   - Logging via `print()` and `FreeCAD.Console.PrintMessage()`
   - Logging of return value types
   - Logging of module file path for debugging

5. **Removed report generation from `export()`**
   - Report creation moved to `Command.py` to execute after file name confirmation in dialog

#### Key Code Lines:
```python
# Return list of tuples instead of string
return [("mpr", mpr_content), ("nc", gcode_content)]

# Validation before return
if not isinstance(result, list):
    # Error handling
    result = [("mpr", str(mpr_content) if mpr_content else ""), ("nc", str(gcode_content) if gcode_content else "")]
```

---

### 2. `/Users/user/Documents/freecad/.pixi/envs/default/Mod/CAM/Path/Post/Processor.py`
**Source:** `/Users/user/Documents/freecad/src/Mod/CAM/Path/Post/Processor.py`

#### Main Changes:

1. **Improved module reloading in `WrapperPost.export()`**
   - **Before:** Used `importlib.reload()`, which didn't work if module wasn't in `sys.modules`
   - **After:** Module is removed from `sys.modules` and reloaded from file to guarantee latest version usage
   - Added logging of module file path

2. **Added list of tuples handling in `WrapperPost.export()`**
   - **Before:** Only traditional string return was handled
   - **After:** Checks if result is a list of tuples
   - If yes, each tuple is added as a separate subpart to `g_code_sections`
   - This allows processing multiple formats (MPR and NC)

3. **Added error handling for unexpected types**
   - Handling of `bool`, `None`, and other unexpected types
   - Error messages to FreeCAD console
   - Prevents crash on incorrect type

4. **Added logging to FreeCAD console**
   - Logging of result type from `export()`
   - Logging of number of elements in list
   - Logging of final `g_code_sections` count

#### Key Code Lines:
```python
# Remove module from sys.modules for forced reload
if self.module_name in sys.modules:
    del sys.modules[self.module_name]

# Handle list of tuples
if isinstance(result, list) and len(result) > 0:
    if isinstance(result[0], tuple):
        for subpart_name, content in result:
            g_code_sections.append((subpart_name, content))
```

---

### 3. `/Users/user/Documents/freecad/.pixi/envs/default/Mod/CAM/Path/Post/Command.py`
**Source:** `/Users/user/Documents/freecad/src/Mod/CAM/Path/Post/Command.py`

#### Main Changes:

1. **Added handling of multiple subparts with same base name**
   - **Problem:** When creating multiple files (MPR and NC), FreeCAD added suffixes `-1`, `-2` to file names
   - **Solution:** Base name is saved after first subpart and reused for all subsequent ones
   - This guarantees both files have the same base name: `Part_Job.mpr` and `Part_Job.nc`

2. **Added file extension determination logic by subpart**
   - If subpart = "mpr", uses `.mpr` extension
   - If subpart = "nc", uses `.nc` extension
   - This allows FreeCAD to correctly determine file extension

3. **Moved report creation from `woodwop_post.py`**
   - Report creation now happens in `Command.py` after all file names are confirmed in dialog
   - Report uses base name from first created file
   - Report is created only for "woodwop" post-processor

4. **Improved file creation process logging**
   - Logging of each subpart processing stage
   - Logging of base name saving and reuse
   - Logging of final file names

#### Key Code Lines:
```python
# Save base name for reuse
if base_filename_for_subparts is None:
    fname = next(generated_filename)
    base_filename_for_subparts, _ = os.path.splitext(fname)
else:
    # Reuse base name
    fname = base_filename_for_subparts + (os.path.splitext(next(generated_filename))[1] or '.nc')
```

---

### 4. `/Users/user/Documents/freecad/.pixi/envs/default/Mod/CAM/Path/Post/Utils.py`
**Source:** `/Users/user/Documents/freecad/src/Mod/CAM/Path/Post/Utils.py`

#### Main Changes:

1. **Added `_get_post_processor_extension()` method**
   - Dynamically loads post-processor module
   - Extracts `FILE_EXTENSION` value from module
   - Used to set correct default extension in save dialog

2. **Added `_get_part_name_from_job()` method**
   - Extracts part name from `Job.Model`, `Job.Base`, or `Stock.Base`
   - Handles various FreeCAD object types (direct objects, lists, references, groups)
   - Searches for objects of type `Part::Feature`, `PartDesign::Body`, `App::Part`
   - Ignores invalid names like `<group object>`
   - **Removes "Model-" prefix from part name**

3. **Improved default filename generation logic**
   - Priority: `part_name` + `job_name` > `PostProcessorOutputFile` > document name
   - Invalid names (starting with `<` or `[`) are ignored
   - Uses extension from post-processor if available

4. **Added global file logging**
   - All `Path.Log` messages are written to file `freecad_postprocess_YYYYMMDD_HHMMSS.log`
   - Logging of each filename generation stage

#### Key Code Lines:
```python
# Remove "Model-" prefix
if part_name.startswith('Model-'):
    part_name = part_name[6:]  # Remove "Model-" (6 characters)

# Priority naming logic
if part_name and job_name:
    filename = f"{part_name}_{job_name}"
```

---

### 5. `/Users/user/Documents/freecad/.pixi/envs/default/Mod/CAM/Path/Tool/Gui/__init__.py`
**Source:** `/Users/user/Documents/freecad/src/Mod/CAM/Path/Tool/Gui/__init__.py`

#### Main Changes:

1. **Added `BitLibrary` compatibility class**
   - Fixes `ImportError: cannot import name 'BitLibrary' from 'Path.Tool.Gui'`
   - Allows old addons (e.g., `btl`) to work with new FreeCAD structure
   - Allows addons to monkey-patch `ToolBitLibrary` attribute

#### Key Code Lines:
```python
# Backward compatibility for addons that use the old BitLibrary API
class BitLibrary:
    """
    Compatibility class for backward compatibility with old addons.
    The ToolBitLibrary attribute can be monkey-patched by addons like 'btl'.
    """
    ToolBitLibrary = None
```

---

## Deleted Files

### `/Users/user/Documents/freecad/woodwop post/woodwop_gcode_post.py`
- Deleted per user request
- G-code generation functionality integrated into `woodwop_post.py`

---

## Change Results

### Before Changes:
- ❌ Post-processor returned only one format (G-code as string)
- ❌ Files were created with incorrect names (`<group object>.mpr`, `<group object>.nc`)
- ❌ Files were created before name confirmation in dialog
- ❌ File names contained "Model-" prefix
- ❌ No project report

### After Changes:
- ✅ Post-processor returns two formats (MPR and NC) as list of tuples
- ✅ Files are created with correct names based on part name and Job (`Part_Job.mpr`, `Part_Job.nc`)
- ✅ Files are created only after name confirmation in dialog
- ✅ "Model-" prefix is automatically removed from file names
- ✅ Project report is automatically created (`Part_Job_job_report.txt`)
- ✅ Both files have the same base name (without `-1`, `-2` suffixes)

---

## Technical Details

### Solution Architecture:

1. **Multiple Formats:**
   - `woodwop_post.py` generates both formats (MPR and NC)
   - Returns list of tuples: `[("mpr", mpr_content), ("nc", gcode_content)]`
   - `Processor.py` processes the list and creates separate subparts
   - `Command.py` creates separate files for each subpart

2. **File Naming:**
   - `Utils.py` extracts part name from Job
   - Removes "Model-" prefix from name
   - Combines with Job name: `{part_name}_{job_name}`
   - `Command.py` saves base name for reuse between subparts

3. **Report Creation:**
   - Report is created in `Command.py` after all file names are confirmed
   - Uses base name from first created file
   - Contains all Job properties for correctness verification

---

## Files for Comparison

For post-processor correctness verification, two files are created:
- `Part_Job.mpr` - WoodWOP MPR format (main format)
- `Part_Job.nc` - Standard G-code format (for comparison)

User can compare contents of these files to correct MPR post-processor.

---

## Logging

All operations are logged to file:
- `freecad_postprocess_YYYYMMDD_HHMMSS.log` - detailed log of all operations

Logs contain:
- Filename generation process
- Each subpart processing
- File creation
- Report creation

---

## Compatibility

- ✅ FreeCAD 1.2.0
- ✅ Python 3.11
- ✅ Backward compatibility with old addons (via `BitLibrary`)

---

## Notes

1. All changes are synchronized between:
   - Installed version: `.pixi/envs/default/Mod/CAM/Path/Post/`
   - Source code: `src/Mod/CAM/Path/Post/`

2. FreeCAD restart is required to apply changes (not just module reload).

3. `woodwop_post` module is forcibly reloaded on each call to guarantee latest version usage.

---

**End of Report**

