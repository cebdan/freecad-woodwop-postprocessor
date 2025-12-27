# WoodWOP Post Processor for FreeCAD
# This post processor converts FreeCAD Path workbench output to WoodWOP MPR format
# for HOMAG CNC machines
# Based on MPR Format 4.0 specification

import FreeCAD
import Path
import PathScripts.PathUtils as PathUtils
import datetime
import math

TOOLTIP = '''
WoodWOP MPR post processor for HOMAG CNC machines.
Converts FreeCAD Path operations to WoodWOP MPR 4.0 format.

The .nc file will be AUTOMATICALLY renamed to .mpr after export!
The .mpr file will be ready almost instantly.

If auto-rename fails, manually rename .nc to .mpr
'''

TOOLTIP_ARGS = '''
--no-comments: Suppress comment output
--precision=X: Set coordinate precision (default 3)
--workpiece-length=X: Workpiece length in mm (default: auto-detect)
--workpiece-width=Y: Workpiece width in mm (default: auto-detect)
--workpiece-thickness=Z: Workpiece thickness in mm (default: auto-detect)
--use-part-name: Name .mpr file after the part/body name instead of document name
--g54: Set coordinate system offset to minimum part coordinates (legacy flag)
  When set, MPR coordinates will be offset by minimum part coordinates (X, Y, Z).
  Origin (0,0,0) will be at the minimum point of the part.
  NOTE: G-code output is NOT affected and remains unchanged.
  PREFERRED: Use Work Coordinate Systems (Fixtures) in Job settings instead of this flag.
  If G54 is checked in Job settings, it will automatically be used.
--log or /log: Enable verbose logging (detailed debug output)
  When set, detailed debug information will be printed to console and log file.
  If not set, only critical errors and warnings are shown.
'''

# File extension for WoodWOP MPR files
# These variables tell FreeCAD what file extension to use
POSTPROCESSOR_FILE_NAME = 'woodwop_post'
FILE_EXTENSION = '.mpr'
UNITS = 'G21'  # Metric units

now = datetime.datetime.now()

# Post processor configuration
PRECISION = 3
OUTPUT_COMMENTS = True
WORKPIECE_LENGTH = None
WORKPIECE_WIDTH = None
WORKPIECE_THICKNESS = None
STOCK_EXTENT_X = 0.0
STOCK_EXTENT_Y = 0.0
USE_PART_NAME = False

# Coordinate system offset (for G54, G55, etc.)
# If set, coordinates will be offset by the minimum part coordinates
# This is ONLY applied to MPR format, G-code remains unchanged
COORDINATE_SYSTEM = None  # None, 'G54', 'G55', 'G56', 'G57', 'G58', 'G59'
COORDINATE_OFFSET_X = 0.0
COORDINATE_OFFSET_Y = 0.0
COORDINATE_OFFSET_Z = 0.0

# Verbose logging flag
ENABLE_VERBOSE_LOGGING = False  # Set to True via /log or --log flag

# Tracking
contour_counter = 1
contours = []
operations = []
tools_used = set()


def debug_log(message):
    """Print debug message only if verbose logging is enabled."""
    if ENABLE_VERBOSE_LOGGING:
        print(message)
        try:
            import FreeCAD
            FreeCAD.Console.PrintMessage(message + "\n")
        except:
            pass


def parse_arguments(argstring):
    """Parse command-line arguments and set global configuration variables.
    
    Args:
        argstring: String containing space-separated arguments (e.g., "--no-comments --precision=3")
    
    Supported arguments:
        --no-comments or /no-comments: Suppress comment output
        --precision=X or /precision=X: Set coordinate precision (default 3)
        --workpiece-length=X: Workpiece length in mm
        --workpiece-width=Y: Workpiece width in mm
        --workpiece-thickness=Z: Workpiece thickness in mm
        --use-part-name or /use-part-name: Name file after part/body name
        --g54 or /g54: Set coordinate system offset (legacy flag)
        --log or /log: Enable verbose logging
    """
    global OUTPUT_COMMENTS, PRECISION
    global WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS, USE_PART_NAME
    global COORDINATE_SYSTEM, ENABLE_VERBOSE_LOGGING
    
    if not argstring:
        return
    
    args = argstring.split()
    for arg in args:
        # Normalize argument to handle both -- and / formats
        normalized_arg = arg.lstrip('-').lstrip('/')
        
        if arg == '--no-comments' or normalized_arg == 'no-comments':
            OUTPUT_COMMENTS = False
        elif arg == '--use-part-name' or normalized_arg == 'use-part-name':
            USE_PART_NAME = True
        elif arg.startswith('--precision=') or normalized_arg.startswith('precision='):
            value = arg.split('=')[1] if '=' in arg else normalized_arg.split('=')[1]
            PRECISION = int(value)
        elif arg.startswith('--workpiece-length=') or normalized_arg.startswith('workpiece-length='):
            value = arg.split('=')[1] if '=' in arg else normalized_arg.split('=')[1]
            WORKPIECE_LENGTH = float(value)
        elif arg.startswith('--workpiece-width=') or normalized_arg.startswith('workpiece-width='):
            value = arg.split('=')[1] if '=' in arg else normalized_arg.split('=')[1]
            WORKPIECE_WIDTH = float(value)
        elif arg.startswith('--workpiece-thickness=') or normalized_arg.startswith('workpiece-thickness='):
            value = arg.split('=')[1] if '=' in arg else normalized_arg.split('=')[1]
            WORKPIECE_THICKNESS = float(value)
        elif arg in ['--g54', '--G54'] or normalized_arg.lower() == 'g54':
            # Legacy flag support - will be overridden by Job.Fixtures if present
            COORDINATE_SYSTEM = 'G54'
            debug_log(f"[WoodWOP DEBUG] Coordinate system set to G54 via {arg} flag (legacy mode)")
        elif arg == '--log' or normalized_arg == 'log':
            ENABLE_VERBOSE_LOGGING = True
            print(f"[WoodWOP] Verbose logging enabled via {arg} flag")
            # Update global variable
            import sys
            current_module = sys.modules.get(__name__)
            if current_module:
                current_module.ENABLE_VERBOSE_LOGGING = True


def collect_contours(objectslist):
    """Process all path objects to extract contours and operations.
    
    Args:
        objectslist: List of FreeCAD Path objects to process
    
    This function populates global variables:
        - contours: List of contour dictionaries
        - operations: List of operation dictionaries
        - tools_used: Set of tool numbers used
        - contour_counter: Counter for contour IDs
    """
    global contour_counter, contours, operations, tools_used
    
    # Reset globals
    contour_counter = 1
    contours = []
    operations = []
    tools_used = set()
    
    # Process all path objects to extract contours and operations
    for obj in objectslist:
        print(f"[WoodWOP DEBUG] Processing object: {obj.Label if hasattr(obj, 'Label') else 'Unknown'}")
        if not hasattr(obj, "Path"):
            print(f"[WoodWOP DEBUG] Object has no Path attribute, skipping")
            continue

        # Check if Path has commands
        try:
            path_commands = PathUtils.getPathWithPlacement(obj).Commands
            print(f"[WoodWOP DEBUG] Found {len(path_commands)} commands in Path")
        except Exception as e:
            print(f"[WoodWOP DEBUG] Error getting commands: {e}")
            if hasattr(obj, 'Path') and hasattr(obj.Path, 'Commands'):
                path_commands = obj.Path.Commands
                print(f"[WoodWOP DEBUG] Using direct Path.Commands: {len(path_commands)} commands")
            else:
                print(f"[WoodWOP DEBUG] No commands found, skipping object")
                continue

        if not path_commands:
            print(f"[WoodWOP DEBUG] Path has no commands, skipping")
            continue

        process_path_object(obj)


def export(objectslist, filename, argstring):
    """Main export function called by FreeCAD.
    
    NOTE: FreeCAD may show a save dialog before calling this function.
    We ignore the filename from that dialog and automatically create files
    based on Model or part name from Job settings.
    
    CRITICAL: This function MUST return a list of tuples: [("mpr", content), ("nc", content)]
    NEVER return bool, None, or string directly.
    """
    # CRITICAL: Ensure we always return a list, never bool or other types
    # This is a safety check at the very beginning
    import sys
    import traceback
    
    global OUTPUT_COMMENTS, PRECISION
    global WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS, USE_PART_NAME
    global STOCK_EXTENT_X, STOCK_EXTENT_Y
    global contour_counter, contours, operations, tools_used
    global COORDINATE_SYSTEM, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y, COORDINATE_OFFSET_Z
    global ENABLE_VERBOSE_LOGGING
    
    # Reset verbose logging flag
    ENABLE_VERBOSE_LOGGING = False
    
    # Debug output - use both print() and FreeCAD.Console to ensure visibility
    debug_log("[WoodWOP DEBUG] ===== export() called =====")
    debug_log(f"[WoodWOP DEBUG] File: {__file__}")
    debug_log(f"[WoodWOP DEBUG] objectslist type: {type(objectslist)}, length: {len(objectslist) if hasattr(objectslist, '__len__') else 'N/A'}")
    debug_log(f"[WoodWOP DEBUG] filename: {filename}")
    debug_log(f"[WoodWOP DEBUG] argstring: {argstring}")
    debug_log("[WoodWOP DEBUG] Files will be created automatically based on Model/part name from Job")

    # Try to get actual output file from Job
    actual_output_file = None
    if filename == '-':
        # FreeCAD is using stdout mode, try to get the real filename from Job
        debug_log("[WoodWOP DEBUG] Searching for output filename...")

        # Method 1: Check objectslist for Job with PostProcessorOutputFile
        for obj in objectslist:
            debug_log(f"[WoodWOP DEBUG] Checking object: {obj.Label if hasattr(obj, 'Label') else 'Unknown'}, type: {type(obj).__name__}")
            if hasattr(obj, 'PostProcessorOutputFile'):
                actual_output_file = obj.PostProcessorOutputFile
                debug_log(f"[WoodWOP DEBUG] Found PostProcessorOutputFile: {actual_output_file}")
                break

        # Method 2: Try to get from FreeCAD Active Document
        if not actual_output_file:
            try:
                import FreeCAD
                doc = FreeCAD.ActiveDocument
                if doc:
                    # Look for Job objects in the document
                    for obj in doc.Objects:
                        if hasattr(obj, 'Proxy') and 'Job' in str(type(obj.Proxy)):
                            if hasattr(obj, 'PostProcessorOutputFile'):
                                actual_output_file = obj.PostProcessorOutputFile
                                debug_log(f"[WoodWOP DEBUG] Found Job output file: {actual_output_file}")

                                # If empty, use a hook to find the file after FreeCAD creates it
                                if not actual_output_file:
                                    # We'll create the .mpr file after FreeCAD writes the .nc file
                                    # by monitoring the file system
                                    actual_output_file = "AUTO_DETECT"
                                    debug_log("[WoodWOP DEBUG] Will auto-detect output file")
                                break
            except Exception as e:
                debug_log(f"[WoodWOP DEBUG] Could not access ActiveDocument: {e}")

    # Reset globals
    contour_counter = 1
    contours = []
    operations = []
    tools_used = set()

    # Parse arguments
    parse_arguments(argstring)

    # Get Job and extract base filename from settings or part name
    job = None
    part_name = None
    job_output_file = None
    job_model = None
    
    for obj in objectslist:
        if hasattr(obj, 'Proxy') and hasattr(obj.Proxy, 'Type'):
            if 'Job' in obj.Proxy.Type:
                job = obj
                # Get PostProcessorOutputFile from Job settings
                if hasattr(obj, 'PostProcessorOutputFile'):
                    job_output_file = obj.PostProcessorOutputFile
                    print(f"[WoodWOP DEBUG] Found PostProcessorOutputFile in Job: {job_output_file}")
                
                # Check Work Coordinate Systems (Fixtures) from Job
                # This is the primary way to determine if G54 (or other WCS) should be used
                if hasattr(obj, 'Fixtures') and obj.Fixtures:
                    fixtures_list = obj.Fixtures
                    print(f"[WoodWOP DEBUG] Found Fixtures in Job: {fixtures_list}")
                    # Check if G54 is in the list
                    if 'G54' in fixtures_list:
                        COORDINATE_SYSTEM = 'G54'
                        print(f"[WoodWOP DEBUG] G54 found in Job.Fixtures - coordinate system set to G54 (minimum part coordinates)")
                    elif len(fixtures_list) > 0:
                        # Use first fixture if G54 is not present (for future support of G55-G59)
                        first_fixture = fixtures_list[0]
                        if first_fixture.startswith('G5'):
                            COORDINATE_SYSTEM = first_fixture
                            print(f"[WoodWOP DEBUG] {first_fixture} found in Job.Fixtures - coordinate system set to {first_fixture}")
                        else:
                            print(f"[WoodWOP DEBUG] Fixture '{first_fixture}' found but not supported yet (only G54-G59 supported)")
                    else:
                        print(f"[WoodWOP DEBUG] Fixtures list is empty - using project coordinate system")
                else:
                    print(f"[WoodWOP DEBUG] Fixtures property not found in Job - checking legacy --g54 flag")
                
                # Try to get Model property from Job
                if hasattr(obj, 'Model'):
                    job_model = obj.Model
                    print(f"[WoodWOP DEBUG] Found Model property in Job: {job_model}")
                elif hasattr(obj, 'ModelName'):
                    job_model = obj.ModelName
                    print(f"[WoodWOP DEBUG] Found ModelName property in Job: {job_model}")
                elif hasattr(obj, 'модел'):
                    job_model = obj.модел
                    print(f"[WoodWOP DEBUG] Found модел property in Job: {job_model}")
                # Try to get from Properties list
                if not job_model and hasattr(obj, 'PropertiesList'):
                    print(f"[WoodWOP DEBUG] Job PropertiesList: {obj.PropertiesList}")
                    for prop in obj.PropertiesList:
                        if 'model' in prop.lower() or 'модел' in prop.lower():
                            job_model = getattr(obj, prop, None)
                            print(f"[WoodWOP DEBUG] Found Model property '{prop}' in Job: {job_model}")
                            break
                    # If still not found, print all properties for debugging
                    if not job_model:
                        print(f"[WoodWOP DEBUG] Model property not found. All Job properties:")
                        for prop in obj.PropertiesList:
                            try:
                                value = getattr(obj, prop, None)
                                print(f"[WoodWOP DEBUG]   {prop} = {value}")
                            except:
                                pass
                
                # Extract part name from Job's Base object (always, not just when USE_PART_NAME)
                if hasattr(obj, 'Base') and obj.Base:
                    print(f"[WoodWOP DEBUG] Job.Base type: {type(obj.Base)}, value: {obj.Base}")
                    # Job.Base can be a single object or a group
                    if hasattr(obj.Base, 'Label'):
                        part_name = obj.Base.Label
                        print(f"[WoodWOP DEBUG] Found part name from Job.Base.Label: {part_name}")
                    elif isinstance(obj.Base, (list, tuple)) and len(obj.Base) > 0:
                        if hasattr(obj.Base[0], 'Label'):
                            part_name = obj.Base[0].Label
                            print(f"[WoodWOP DEBUG] Found part name from Job.Base[0].Label: {part_name}")
                    # Try to get name from document object if Base is a reference
                    if not part_name:
                        try:
                            import FreeCAD
                            doc = FreeCAD.ActiveDocument
                            if doc:
                                # Try to find the actual object in document
                                base_obj = None
                                if hasattr(obj.Base, 'Name'):
                                    base_obj = doc.getObject(obj.Base.Name)
                                elif isinstance(obj.Base, (list, tuple)) and len(obj.Base) > 0:
                                    if hasattr(obj.Base[0], 'Name'):
                                        base_obj = doc.getObject(obj.Base[0].Name)
                                
                                if base_obj and hasattr(base_obj, 'Label'):
                                    part_name = base_obj.Label
                                    print(f"[WoodWOP DEBUG] Found part name from document object: {part_name}")
                                
                                # Also try to find Body object which might contain the part
                                for doc_obj in doc.Objects:
                                    if hasattr(doc_obj, 'Proxy') and 'Body' in str(type(doc_obj.Proxy)):
                                        if hasattr(doc_obj, 'Label'):
                                            part_name = doc_obj.Label
                                            print(f"[WoodWOP DEBUG] Found part name from Body object: {part_name}")
                                            break
                        except Exception as e:
                            print(f"[WoodWOP DEBUG] Error extracting part name: {e}")
                break
    
    # Also try to get Job from ActiveDocument if not found in objectslist
    if not job:
        try:
            import FreeCAD
            doc = FreeCAD.ActiveDocument
            if doc:
                for obj in doc.Objects:
                    if hasattr(obj, 'Proxy') and 'Job' in str(type(obj.Proxy)):
                        job = obj
                        if hasattr(obj, 'PostProcessorOutputFile'):
                            job_output_file = obj.PostProcessorOutputFile
                            print(f"[WoodWOP DEBUG] Found PostProcessorOutputFile in ActiveDocument Job: {job_output_file}")
                        
                        # Check Work Coordinate Systems (Fixtures) from Job
                        # This is the primary way to determine if G54 (or other WCS) should be used
                        if hasattr(obj, 'Fixtures') and obj.Fixtures:
                            fixtures_list = obj.Fixtures
                            print(f"[WoodWOP DEBUG] Found Fixtures in ActiveDocument Job: {fixtures_list}")
                            # Check if G54 is in the list
                            if 'G54' in fixtures_list:
                                COORDINATE_SYSTEM = 'G54'
                                print(f"[WoodWOP DEBUG] G54 found in ActiveDocument Job.Fixtures - coordinate system set to G54 (minimum part coordinates)")
                            elif len(fixtures_list) > 0:
                                # Use first fixture if G54 is not present (for future support of G55-G59)
                                first_fixture = fixtures_list[0]
                                if first_fixture.startswith('G5'):
                                    COORDINATE_SYSTEM = first_fixture
                                    print(f"[WoodWOP DEBUG] {first_fixture} found in ActiveDocument Job.Fixtures - coordinate system set to {first_fixture}")
                                else:
                                    print(f"[WoodWOP DEBUG] Fixture '{first_fixture}' found but not supported yet (only G54-G59 supported)")
                            else:
                                print(f"[WoodWOP DEBUG] Fixtures list is empty - using project coordinate system")
                        else:
                            print(f"[WoodWOP DEBUG] Fixtures property not found in ActiveDocument Job - checking legacy --g54 flag")
                        
                        # Try to get Model property from Job
                        if not job_model:
                            if hasattr(obj, 'Model'):
                                job_model = obj.Model
                                print(f"[WoodWOP DEBUG] Found Model property in ActiveDocument Job: {job_model}")
                            elif hasattr(obj, 'ModelName'):
                                job_model = obj.ModelName
                                print(f"[WoodWOP DEBUG] Found ModelName property in ActiveDocument Job: {job_model}")
                            elif hasattr(obj, 'модел'):
                                job_model = obj.модел
                                print(f"[WoodWOP DEBUG] Found модел property in ActiveDocument Job: {job_model}")
                            # Try to get from Properties list
                            if not job_model and hasattr(obj, 'PropertiesList'):
                                print(f"[WoodWOP DEBUG] ActiveDocument Job PropertiesList: {obj.PropertiesList}")
                                for prop in obj.PropertiesList:
                                    if 'model' in prop.lower() or 'модел' in prop.lower():
                                        job_model = getattr(obj, prop, None)
                                        print(f"[WoodWOP DEBUG] Found Model property '{prop}' in ActiveDocument Job: {job_model}")
                                        break
                                # If still not found, print all properties for debugging
                                if not job_model:
                                    print(f"[WoodWOP DEBUG] Model property not found. All ActiveDocument Job properties:")
                                    for prop in obj.PropertiesList:
                                        try:
                                            value = getattr(obj, prop, None)
                                            print(f"[WoodWOP DEBUG]   {prop} = {value}")
                                        except:
                                            pass
                        if hasattr(obj, 'Base') and obj.Base:
                            print(f"[WoodWOP DEBUG] ActiveDocument Job.Base type: {type(obj.Base)}, value: {obj.Base}")
                            if hasattr(obj.Base, 'Label'):
                                part_name = obj.Base.Label
                                print(f"[WoodWOP DEBUG] Found part name from ActiveDocument Job.Base.Label: {part_name}")
                            elif isinstance(obj.Base, (list, tuple)) and len(obj.Base) > 0:
                                if hasattr(obj.Base[0], 'Label'):
                                    part_name = obj.Base[0].Label
                                    print(f"[WoodWOP DEBUG] Found part name from ActiveDocument Job.Base[0].Label: {part_name}")
                            
                            # Try to get from document object
                            if not part_name:
                                base_obj = None
                                if hasattr(obj.Base, 'Name'):
                                    base_obj = doc.getObject(obj.Base.Name)
                                elif isinstance(obj.Base, (list, tuple)) and len(obj.Base) > 0:
                                    if hasattr(obj.Base[0], 'Name'):
                                        base_obj = doc.getObject(obj.Base[0].Name)
                                
                                if base_obj and hasattr(base_obj, 'Label'):
                                    part_name = base_obj.Label
                                    print(f"[WoodWOP DEBUG] Found part name from ActiveDocument object: {part_name}")
                        break
        except Exception as e:
            print(f"[WoodWOP DEBUG] Could not access ActiveDocument: {e}")
    
    # Determine base filename: PostProcessorOutputFile (with path) -> Model -> Part name -> PostProcessorOutputFile (name only) -> filename
    base_filename = None
    import os
    
    # Debug: Print all collected values
    print(f"[WoodWOP DEBUG] ===== Determining base filename =====")
    print(f"[WoodWOP DEBUG] job_output_file: {job_output_file}")
    print(f"[WoodWOP DEBUG] job_model: {job_model}")
    print(f"[WoodWOP DEBUG] part_name: {part_name}")
    print(f"[WoodWOP DEBUG] filename from dialog: {filename}")
    
    # Priority 1: PostProcessorOutputFile from Job settings (only if it contains a full path)
    if job_output_file and job_output_file.strip():
        # Check if it contains a path (not just a filename)
        dir_name = os.path.dirname(job_output_file)
        if dir_name and dir_name != '/' and dir_name != '.':
            # Contains a valid path, use it
            base_name = os.path.splitext(os.path.basename(job_output_file))[0]
            if base_name:
                base_filename = base_name
                print(f"[WoodWOP DEBUG] Priority 1: Using base name from PostProcessorOutputFile (with path): {base_filename}")
        else:
            # Only filename without path, treat as empty and use Model or part name instead
            print(f"[WoodWOP DEBUG] PostProcessorOutputFile contains only filename without path, will use Model or part name instead")
    
    # Priority 2: Model from Job (highest priority for user-defined model name)
    if not base_filename:
        if job_model:
            model_str = str(job_model).strip()
            if model_str:
                base_filename = model_str
                print(f"[WoodWOP DEBUG] Priority 2: Using Model from Job as base filename: {base_filename}")
            else:
                print(f"[WoodWOP DEBUG] Model found but is empty/whitespace")
        else:
            print(f"[WoodWOP DEBUG] Model not found in Job")
    
    # Priority 3: Part name (use this if PostProcessorOutputFile is empty or just a filename, and Model is not set)
    if not base_filename:
        if part_name:
            part_str = part_name.strip()
            if part_str:
                base_filename = part_str
                print(f"[WoodWOP DEBUG] Priority 3: Using part name as base filename: {base_filename}")
            else:
                print(f"[WoodWOP DEBUG] Part name found but is empty/whitespace")
        else:
            print(f"[WoodWOP DEBUG] Part name not found")
    
    # Priority 4: PostProcessorOutputFile if it's just a filename (fallback if Model and part name are not set)
    if not base_filename and job_output_file and job_output_file.strip():
        base_name = os.path.splitext(os.path.basename(job_output_file))[0]
        if base_name:
            base_filename = base_name
            print(f"[WoodWOP DEBUG] Priority 4: Using base name from PostProcessorOutputFile (filename only): {base_filename}")
    
    # Priority 5: Fallback to filename from dialog (ONLY if nothing else was found)
    # NOTE: We try to avoid using dialog filename - prefer Model or part name
    if not base_filename and filename and filename != '-':
        # Remove any extension and path to get base name
        if '.' in filename:
            base_filename = os.path.splitext(os.path.basename(filename))[0]
        else:
            base_filename = os.path.basename(filename)
        print(f"[WoodWOP DEBUG] Priority 5: Using base name from filename dialog: {base_filename}")
        print(f"[WoodWOP DEBUG] WARNING: Using dialog filename - consider setting Model in Job or part name")
    elif filename and filename != '-':
        dialog_name = os.path.splitext(os.path.basename(filename))[0] if '.' in filename else os.path.basename(filename)
        print(f"[WoodWOP DEBUG] Filename from dialog '{dialog_name}' ignored (using higher priority source: {base_filename})")
    
    # Final fallback
    if not base_filename:
        base_filename = "export"
        print(f"[WoodWOP DEBUG] Using default base filename: {base_filename}")
    
    # Get directory for output files
    # NOTE: We ignore filename from dialog - always use Job settings or document directory
    output_dir = None
    if job_output_file and job_output_file.strip():
        # Check if job_output_file contains a path
        if os.path.dirname(job_output_file):
            # Contains a path, use it
            output_dir = os.path.dirname(os.path.abspath(job_output_file))
        else:
            # Only filename, use document directory or current directory
            try:
                import FreeCAD
                doc = getattr(FreeCAD, "ActiveDocument", None)
                if doc and doc.FileName:
                    output_dir = os.path.dirname(doc.FileName)
                else:
                    output_dir = os.getcwd()
            except:
                output_dir = os.getcwd()
    else:
        # Use document directory or current directory
        try:
            import FreeCAD
            doc = getattr(FreeCAD, "ActiveDocument", None)
            if doc and doc.FileName:
                output_dir = os.path.dirname(doc.FileName)
            else:
                output_dir = os.getcwd()
        except:
            output_dir = os.getcwd()
    
    # Final check - ensure we have a valid directory (not root)
    if not output_dir or output_dir == '/' or not os.path.isdir(output_dir):
        output_dir = os.getcwd()
    
    print(f"[WoodWOP DEBUG] Base filename (without extension): {base_filename}")
    print(f"[WoodWOP DEBUG] Output directory: {output_dir}")
    print(f"[WoodWOP DEBUG] Will create: {os.path.join(output_dir, base_filename + '.mpr')} and {os.path.join(output_dir, base_filename + '.nc')}")

    # Auto-detect workpiece dimensions if not specified
    if job and hasattr(job, 'Stock'):
        stock = job.Stock
        if WORKPIECE_LENGTH is None and hasattr(stock, 'Length'):
            WORKPIECE_LENGTH = stock.Length.Value
        if WORKPIECE_WIDTH is None and hasattr(stock, 'Width'):
            WORKPIECE_WIDTH = stock.Width.Value
        if WORKPIECE_THICKNESS is None and hasattr(stock, 'Height'):
            WORKPIECE_THICKNESS = stock.Height.Value

        # Get stock extents for raw material calculations
        if hasattr(stock, 'ExtentXPos'):
            STOCK_EXTENT_X = stock.ExtentXPos.Value
        if hasattr(stock, 'ExtentYPos'):
            STOCK_EXTENT_Y = stock.ExtentYPos.Value

    # Set defaults if still None
    if WORKPIECE_LENGTH is None:
        WORKPIECE_LENGTH = 800.0
    if WORKPIECE_WIDTH is None:
        WORKPIECE_WIDTH = 600.0
    if WORKPIECE_THICKNESS is None:
        WORKPIECE_THICKNESS = 20.0

    # Collect contours and operations from path objects
    collect_contours(objectslist)

    # Generate MPR content
    print(f"[WoodWOP DEBUG] Generating MPR content...")
    print(f"[WoodWOP DEBUG] Found {len(contours)} contours, {len(operations)} operations")
    print(f"[WoodWOP DEBUG] Contours: {[c['id'] for c in contours]}")
    print(f"[WoodWOP DEBUG] Operations: {[op['type'] for op in operations]}")
    
    if len(contours) == 0 and len(operations) == 0:
        print(f"[WoodWOP WARNING] No contours or operations found! Check if Path objects have commands.")
        print(f"[WoodWOP WARNING] This will create an empty MPR file with only header and workpiece definition.")
    
    # Calculate coordinate offset if G54 or other coordinate system flag is set
    # This offset will be applied ONLY to MPR format, G-code remains unchanged
    if COORDINATE_SYSTEM:
        min_x, min_y, min_z = calculate_part_minimum()
        COORDINATE_OFFSET_X = -min_x
        COORDINATE_OFFSET_Y = -min_y
        COORDINATE_OFFSET_Z = -min_z
        print(f"[WoodWOP DEBUG] {COORDINATE_SYSTEM} coordinate system enabled")
        print(f"[WoodWOP DEBUG] Part minimum: X={min_x:.3f}, Y={min_y:.3f}, Z={min_z:.3f}")
        print(f"[WoodWOP DEBUG] Coordinate offset: X={COORDINATE_OFFSET_X:.3f}, Y={COORDINATE_OFFSET_Y:.3f}, Z={COORDINATE_OFFSET_Z:.3f}")
        print(f"[WoodWOP DEBUG] NOTE: Offset will be applied ONLY to MPR format, G-code remains unchanged")
    else:
        COORDINATE_OFFSET_X = 0.0
        COORDINATE_OFFSET_Y = 0.0
        COORDINATE_OFFSET_Z = 0.0
        print(f"[WoodWOP DEBUG] Using project coordinate system (no offset)")
    
    mpr_content = generate_mpr_content()
    # Validate MPR content
    if not isinstance(mpr_content, str):
        print(f"[WoodWOP ERROR] generate_mpr_content() returned {type(mpr_content)} instead of string: {mpr_content}")
        raise ValueError(f"generate_mpr_content() returned {type(mpr_content)} instead of string")
    print(f"[WoodWOP DEBUG] Generated {len(mpr_content)} characters")
    print(f"[WoodWOP DEBUG] First 200 chars of MPR: {mpr_content[:200]}")
    
    # Generate G-code content in parallel
    print(f"[WoodWOP DEBUG] Generating G-code content...")
    gcode_content = generate_gcode(objectslist)
    # Validate G-code content
    if not isinstance(gcode_content, str):
        print(f"[WoodWOP ERROR] generate_gcode() returned {type(gcode_content)} instead of string: {gcode_content}")
        raise ValueError(f"generate_gcode() returned {type(gcode_content)} instead of string")
    print(f"[WoodWOP DEBUG] Generated {len(gcode_content)} characters of G-code")

    # NOTE: DO NOT create files here - let FreeCAD handle file creation based on returned list
    # Report creation is moved to Command.py to ensure it happens AFTER user confirms filename in dialog
    
    # Return list of tuples: [(subpart_name, content), ...]
    # FreeCAD will create separate files for each tuple
    # Format: [("mpr", mpr_content), ("nc", gcode_content)]
    # FreeCAD will use subpart_name to determine file extension
    print(f"[WoodWOP DEBUG] Returning both MPR and NC formats to FreeCAD")
    print(f"[WoodWOP DEBUG] MPR content type: {type(mpr_content)}, length: {len(mpr_content)} characters")
    print(f"[WoodWOP DEBUG] G-code content type: {type(gcode_content)}, length: {len(gcode_content)} characters")
    
    # CRITICAL: Build result list and verify it's correct
    result = [("mpr", mpr_content), ("nc", gcode_content)]
    
    # CRITICAL: Verify result is a list before returning
    if not isinstance(result, list):
        error_msg = f"[WoodWOP ERROR] result is not a list! Type: {type(result)}, value: {result}"
        print(error_msg)
        try:
            import FreeCAD
            FreeCAD.Console.PrintError(f"{error_msg}\n")
            import traceback
            FreeCAD.Console.PrintError(f"Traceback:\n{traceback.format_exc()}\n")
        except:
            pass
        # Force return a list
        result = [("mpr", str(mpr_content) if mpr_content else ""), ("nc", str(gcode_content) if gcode_content else "")]
    
    # Verify each element is a tuple
    for idx, item in enumerate(result):
        if not isinstance(item, tuple) or len(item) != 2:
            error_msg = f"[WoodWOP ERROR] result[{idx}] is not a tuple of 2 elements! Type: {type(item)}, value: {item}"
            print(error_msg)
            try:
                import FreeCAD
                FreeCAD.Console.PrintError(f"{error_msg}\n")
            except:
                pass
            # Fix the item
            if isinstance(item, tuple) and len(item) == 1:
                result[idx] = (item[0], "")
            elif not isinstance(item, tuple):
                result[idx] = (f"item{idx}", str(item) if item else "")
    
    print(f"[WoodWOP DEBUG] Return value type: {type(result)}, length: {len(result)}")
    print(f"[WoodWOP DEBUG] Return value preview: {str(result)[:200]}...")
    print(f"[WoodWOP DEBUG] ===== export() returning =====")
    
    try:
        import FreeCAD
        FreeCAD.Console.PrintMessage(f"[WoodWOP DEBUG] Returning list with {len(result)} items: {[item[0] for item in result]}\n")
        FreeCAD.Console.PrintMessage(f"[WoodWOP DEBUG] Return value type: {type(result).__name__}\n")
    except:
        pass
    
    # FINAL CHECK: This should NEVER be True, but if it is, we'll catch it
    if result is True or result is False:
        error_msg = f"[WoodWOP CRITICAL ERROR] result is a boolean! This should NEVER happen! Value: {result}"
        print(error_msg)
        try:
            import FreeCAD
            FreeCAD.Console.PrintError(f"{error_msg}\n")
            import traceback
            FreeCAD.Console.PrintError(f"Traceback:\n{traceback.format_exc()}\n")
        except:
            pass
        # Return empty list as fallback
        return [("mpr", ""), ("nc", "")]
    
    return result


def create_job_report(job, report_filename):
    """Create a detailed report of all Job properties."""
    import datetime
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("FreeCAD Path Job Properties Report")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Post Processor: WoodWOP MPR")
    report_lines.append("")
    
    # Basic Job information
    report_lines.append("-" * 80)
    report_lines.append("BASIC INFORMATION")
    report_lines.append("-" * 80)
    if hasattr(job, 'Label'):
        report_lines.append(f"Label: {job.Label}")
    if hasattr(job, 'Name'):
        report_lines.append(f"Name: {job.Name}")
    if hasattr(job, 'TypeId'):
        report_lines.append(f"TypeId: {job.TypeId}")
    report_lines.append("")
    
    # All properties
    report_lines.append("-" * 80)
    report_lines.append("ALL PROPERTIES")
    report_lines.append("-" * 80)
    
    if hasattr(job, 'PropertiesList'):
        for prop_name in sorted(job.PropertiesList):
            try:
                prop_value = getattr(job, prop_name, None)
                
                # Format value based on type
                if prop_value is None:
                    value_str = "None"
                elif isinstance(prop_value, (list, tuple)):
                    value_str = f"[{', '.join(str(v) for v in prop_value)}]"
                elif isinstance(prop_value, dict):
                    value_str = f"{{{', '.join(f'{k}: {v}' for k, v in prop_value.items())}}}"
                elif hasattr(prop_value, 'Value'):
                    # FreeCAD property with Value attribute
                    value_str = f"{prop_value.Value} {prop_value.Unit if hasattr(prop_value, 'Unit') else ''}"
                elif hasattr(prop_value, 'Label'):
                    value_str = f"{prop_value.Label} (Name: {prop_value.Name if hasattr(prop_value, 'Name') else 'N/A'})"
                else:
                    value_str = str(prop_value)
                
                # Truncate very long values
                if len(value_str) > 200:
                    value_str = value_str[:200] + "... (truncated)"
                
                report_lines.append(f"{prop_name}: {value_str}")
            except Exception as e:
                report_lines.append(f"{prop_name}: <Error reading property: {e}>")
    else:
        report_lines.append("PropertiesList not available")
    
    report_lines.append("")
    
    # Special properties of interest
    report_lines.append("-" * 80)
    report_lines.append("SPECIAL PROPERTIES OF INTEREST")
    report_lines.append("-" * 80)
    
    special_props = [
        'PostProcessorOutputFile',
        'Model',
        'ModelName',
        'модел',
        'Base',
        'Stock',
        'ToolController',
        'Operations',
        'SetupSheet',
        'CutMaterial',
    ]
    
    for prop_name in special_props:
        if hasattr(job, prop_name):
            try:
                prop_value = getattr(job, prop_name, None)
                if prop_value is not None:
                    if hasattr(prop_value, 'Label'):
                        report_lines.append(f"{prop_name}: {prop_value.Label} (Name: {prop_value.Name if hasattr(prop_value, 'Name') else 'N/A'})")
                    elif isinstance(prop_value, (list, tuple)):
                        report_lines.append(f"{prop_name}: List/Tuple with {len(prop_value)} items")
                        for idx, item in enumerate(prop_value[:10]):  # Show first 10 items
                            if hasattr(item, 'Label'):
                                report_lines.append(f"  [{idx}]: {item.Label}")
                            else:
                                report_lines.append(f"  [{idx}]: {item}")
                        if len(prop_value) > 10:
                            report_lines.append(f"  ... and {len(prop_value) - 10} more items")
                    else:
                        report_lines.append(f"{prop_name}: {prop_value}")
            except Exception as e:
                report_lines.append(f"{prop_name}: <Error: {e}>")
        else:
            report_lines.append(f"{prop_name}: <Not found>")
    
    report_lines.append("")
    
    # Stock information
    if hasattr(job, 'Stock') and job.Stock:
        report_lines.append("-" * 80)
        report_lines.append("STOCK INFORMATION")
        report_lines.append("-" * 80)
        stock = job.Stock
        if hasattr(stock, 'PropertiesList'):
            for prop_name in sorted(stock.PropertiesList):
                try:
                    prop_value = getattr(stock, prop_name, None)
                    if prop_value is not None:
                        if hasattr(prop_value, 'Value'):
                            value_str = f"{prop_value.Value} {prop_value.Unit if hasattr(prop_value, 'Unit') else ''}"
                        else:
                            value_str = str(prop_value)
                        report_lines.append(f"Stock.{prop_name}: {value_str}")
                except Exception as e:
                    report_lines.append(f"Stock.{prop_name}: <Error: {e}>")
    
    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append("End of Report")
    report_lines.append("=" * 80)
    
    # Write report to file
    try:
        with open(report_filename, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(report_lines))
    except Exception as e:
        raise Exception(f"Failed to write report file: {e}")


def process_path_object(obj):
    """Process a single FreeCAD Path object."""
    global contours, operations, tools_used, contour_counter

    # Determine operation type
    op_type = get_operation_type(obj)

    if op_type == 'profile' or op_type == 'contour':
        # Create contour and routing operation
        contour_id = contour_counter
        contour_counter += 1

        contour_elements, start_pos = extract_contour_from_path(obj)
        if contour_elements:
            contours.append({
                'id': contour_id,
                'elements': contour_elements,
                'start_pos': start_pos,
                'label': obj.Label if hasattr(obj, 'Label') else f'Contour{contour_id}'
            })

            # Create Contourfraesen operation
            tool_number = get_tool_number(obj)
            if tool_number:
                tools_used.add(tool_number)

            operations.append(create_contour_milling(obj, contour_id, tool_number))

    elif op_type == 'drilling':
        # Create drilling operations
        drill_ops = extract_drilling_operations(obj)
        operations.extend(drill_ops)

        tool_number = get_tool_number(obj)
        if tool_number:
            tools_used.add(tool_number)

    elif op_type == 'pocket':
        # Create contour for pocket and pocket operation
        contour_id = contour_counter
        contour_counter += 1

        contour_elements, start_pos = extract_contour_from_path(obj)
        if contour_elements:
            contours.append({
                'id': contour_id,
                'elements': contour_elements,
                'start_pos': start_pos,
                'label': obj.Label if hasattr(obj, 'Label') else f'Pocket{contour_id}'
            })

            tool_number = get_tool_number(obj)
            if tool_number:
                tools_used.add(tool_number)

            operations.append(create_pocket_milling(obj, contour_id, tool_number))


def get_operation_type(obj):
    """Determine the type of operation from FreeCAD Path object."""
    if hasattr(obj, 'Proxy') and hasattr(obj.Proxy, 'Type'):
        obj_type = obj.Proxy.Type.lower()
        if 'profile' in obj_type or 'contour' in obj_type:
            return 'profile'
        elif 'drill' in obj_type:
            return 'drilling'
        elif 'pocket' in obj_type:
            return 'pocket'

    # Fallback: analyze path commands
    if hasattr(obj, 'Path'):
        try:
            path_commands = PathUtils.getPathWithPlacement(obj).Commands
            has_arcs = any(cmd.Name in ['G2', 'G02', 'G3', 'G03'] for cmd in path_commands)
            has_drilling = any(cmd.Name in ['G81', 'G82', 'G83'] for cmd in path_commands)

            if has_drilling:
                return 'drilling'
            elif has_arcs:
                return 'profile'
        except:
            # Fallback to direct Path access
            if hasattr(obj.Path, 'Commands'):
                has_arcs = any(cmd.Name in ['G2', 'G02', 'G3', 'G03'] for cmd in obj.Path.Commands)
                has_drilling = any(cmd.Name in ['G81', 'G82', 'G83'] for cmd in obj.Path.Commands)

                if has_drilling:
                    return 'drilling'
                elif has_arcs:
                    return 'profile'

    return 'contour'


def get_tool_number(obj):
    """Extract tool number from Path object."""
    if hasattr(obj, 'ToolController'):
        tc = obj.ToolController
        if hasattr(tc, 'ToolNumber'):
            return tc.ToolNumber
        elif hasattr(tc, 'Tool') and hasattr(tc.Tool, 'ToolNumber'):
            return tc.Tool.ToolNumber

    # Try to find T command in path
    if hasattr(obj, 'Path'):
        try:
            path_commands = PathUtils.getPathWithPlacement(obj).Commands
        except:
            path_commands = obj.Path.Commands if hasattr(obj.Path, 'Commands') else []
        
        for cmd in path_commands:
            if cmd.Name.startswith('T'):
                try:
                    return int(cmd.Name[1:])
                except:
                    pass

    return 101  # Default tool number


def extract_contour_from_path(obj):
    """Extract contour elements (points, lines, arcs) from Path commands."""
    elements = []
    current_x = 0.0
    current_y = 0.0
    current_z = 0.0
    start_x = None
    start_y = None
    start_z = None

    if not hasattr(obj, 'Path'):
        return elements, (0.0, 0.0, 0.0)

    # Use PathUtils.getPathWithPlacement to get commands with placement transformation
    path_commands = PathUtils.getPathWithPlacement(obj).Commands
    if not path_commands:
        return elements, (0.0, 0.0, 0.0)

    for cmd in path_commands:
        params = cmd.Parameters

        # Update position
        x = params.get('X', current_x)
        y = params.get('Y', current_y)
        z = params.get('Z', current_z)

        # Save start position from first movement command
        if start_x is None and cmd.Name in ['G0', 'G00', 'G1', 'G01', 'G2', 'G02', 'G3', 'G03']:
            start_x = current_x
            start_y = current_y
            start_z = current_z

        # Linear move (G1) - create line
        if cmd.Name in ['G1', 'G01']:
            if abs(x - current_x) > 0.001 or abs(y - current_y) > 0.001:
                line_elem = {
                    'type': 'KL',  # Line
                    'x': x,
                    'y': y,
                    'z': z  # Always include Z coordinate
                }
                elements.append(line_elem)

        # Arc move (G2, G3) - create arc
        elif cmd.Name in ['G2', 'G02', 'G3', 'G03']:
            i = params.get('I', 0)
            j = params.get('J', 0)
            direction = 'CW' if cmd.Name in ['G2', 'G02'] else 'CCW'

            # WoodWOP limitation: arcs do not support Z-axis changes
            # If Z changes during arc, we must convert to line segments
            z_changes = abs(z - current_z) > 0.001

            if z_changes:
                # Convert arc with Z change to line segments
                # Calculate center point
                center_x = current_x + i
                center_y = current_y + j
                radius = math.sqrt(i*i + j*j) if (i != 0 or j != 0) else 0

                # Discretize arc into line segments
                # Calculate and normalize arc angles using helper function
                start_angle, end_angle = calculate_arc_angles(current_x, current_y, center_x, center_y, x, y, direction)

                # Number of segments (more segments = smoother curve)
                num_segments = max(8, int(abs(end_angle - start_angle) * 180 / math.pi / 5))  # ~5 degrees per segment

                for seg in range(1, num_segments + 1):
                    t = seg / num_segments
                    angle = start_angle + (end_angle - start_angle) * t
                    seg_x = center_x + radius * math.cos(angle)
                    seg_y = center_y + radius * math.sin(angle)
                    seg_z = current_z + (z - current_z) * t

                    line_elem = {
                        'type': 'KL',  # Line
                        'x': seg_x,
                        'y': seg_y,
                        'z': seg_z
                    }
                    elements.append(line_elem)
            else:
                # Normal arc in XY plane - no Z change
                # Calculate center point (I, J are offsets from start point)
                center_x = current_x + i
                center_y = current_y + j
                radius = math.sqrt(i*i + j*j) if (i != 0 or j != 0) else 0

                # Calculate intermediate point for three-point arc format (X2, Y2)
                # Use midpoint of arc as intermediate point
                # Calculate and normalize arc angles using helper function
                start_angle, end_angle = calculate_arc_angles(current_x, current_y, center_x, center_y, x, y, direction)
                
                mid_angle = (start_angle + end_angle) / 2
                mid_x = center_x + radius * math.cos(mid_angle)
                mid_y = center_y + radius * math.sin(mid_angle)

                arc_elem = {
                'type': 'KA',  # Arc
                    'x': x,  # End point X
                    'y': y,  # End point Y
                    'i': i,  # Center offset in X (from start point)
                    'j': j,  # Center offset in Y (from start point)
                    'x2': mid_x,  # Intermediate point X (for three-point format)
                    'y2': mid_y,  # Intermediate point Y (for three-point format)
                'r': radius,
                    'direction': direction,
                    'z': z  # Always include Z coordinate
                }
                elements.append(arc_elem)

        current_x = x
        current_y = y
        current_z = z

    # Return elements and start position
    start_pos = (start_x if start_x is not None else 0.0,
                 start_y if start_y is not None else 0.0,
                 start_z if start_z is not None else 0.0)
    return elements, start_pos


def extract_drilling_operations(obj):
    """Extract drilling positions from Path object."""
    drilling_ops = []
    tool_number = get_tool_number(obj)

    if not hasattr(obj, 'Path'):
        return drilling_ops

    # Use PathUtils.getPathWithPlacement to get commands with placement transformation
    try:
        path_commands = PathUtils.getPathWithPlacement(obj).Commands
    except:
        path_commands = obj.Path.Commands if hasattr(obj.Path, 'Commands') else []

    if not path_commands:
        return drilling_ops

    # Collect drilling positions
    drill_positions = []
    current_x = 0.0
    current_y = 0.0
    current_z = 0.0
    depth = 10.0

    for cmd in path_commands:
        params = cmd.Parameters

        if cmd.Name in ['G81', 'G82', 'G83']:  # Drilling cycles
            x = params.get('X', current_x)
            y = params.get('Y', current_y)
            z = params.get('Z', current_z)
            r = params.get('R', 0)  # Retract height

            drill_depth = abs(z - r) if r != 0 else abs(z)

            drill_positions.append({
                'x': x,
                'y': y,
                'depth': drill_depth
            })

            current_x = x
            current_y = y
            depth = drill_depth

        elif cmd.Name in ['G0', 'G00', 'G1', 'G01']:
            current_x = params.get('X', current_x)
            current_y = params.get('Y', current_y)
            current_z = params.get('Z', current_z)

    # Create BohrVert (vertical drilling) operation for each position
    for pos in drill_positions:
        drilling_ops.append({
            'type': 'BohrVert',
            'id': 102,
            'xa': pos['x'],
            'ya': pos['y'],
            'depth': pos['depth'],
            'tool': tool_number
        })

    return drilling_ops


def create_contour_milling(obj, contour_id, tool_number):
    """Create Contourfraesen (contour milling) operation."""
    return {
        'type': 'Contourfraesen',
        'id': 105,
        'contour': contour_id,
        'tool': tool_number,
        'label': obj.Label if hasattr(obj, 'Label') else 'Contour Milling'
    }


def create_pocket_milling(obj, contour_id, tool_number):
    """Create Pocket (pocket milling) operation."""
    return {
        'type': 'Pocket',
        'id': 107,
        'contour': contour_id,
        'tool': tool_number,
        'label': obj.Label if hasattr(obj, 'Label') else 'Pocket'
    }


def calculate_part_minimum():
    """Calculate minimum X, Y, Z coordinates from all contours and operations.
    
    This finds the minimum point (intersection of minimum X, Y, Z) which will be used
    as the origin (0,0,0) when G54 or other coordinate system flags are set.
    
    The function checks:
    - Start positions of all contours
    - All line and arc end points
    - Arc center points (for complete arc coverage)
    - Drilling operation positions
    
    Returns:
        tuple: (min_x, min_y, min_z) or (0.0, 0.0, 0.0) if no coordinates found
    """
    global contours, operations
    
    min_x = None
    min_y = None
    min_z = None
    
    points_checked = 0
    
    # Check all contour elements
    for contour_idx, contour in enumerate(contours):
        # Check start position
        start_x, start_y, start_z = contour.get('start_pos', (0.0, 0.0, 0.0))
        if min_x is None or start_x < min_x:
            min_x = start_x
        if min_y is None or start_y < min_y:
            min_y = start_y
        if min_z is None or start_z < min_z:
            min_z = start_z
        points_checked += 1
        
        # Track previous point for arc center calculation
        prev_x = start_x
        prev_y = start_y
        prev_z = start_z
        
        # Check all elements in contour
        for elem_idx, elem in enumerate(contour.get('elements', [])):
            x = elem.get('x', 0.0)
            y = elem.get('y', 0.0)
            z = elem.get('z', 0.0)
            
            # Check end point
            if min_x is None or x < min_x:
                min_x = x
            if min_y is None or y < min_y:
                min_y = y
            if min_z is None or z < min_z:
                min_z = z
            points_checked += 1
            
            # For arcs, also check center point (I, J are relative to previous point)
            if elem.get('type') == 'KA':  # Arc element
                center_x = prev_x + elem.get('i', 0.0)
                center_y = prev_y + elem.get('j', 0.0)
                center_z = prev_z  # Arc center Z is same as previous Z for XY plane arcs
                
                # Check center point
                if min_x is None or center_x < min_x:
                    min_x = center_x
                if min_y is None or center_y < min_y:
                    min_y = center_y
                if min_z is None or center_z < min_z:
                    min_z = center_z
                points_checked += 1
                
                # For arcs, also check if radius extends beyond end point
                # Calculate arc extent (center ± radius)
                radius = elem.get('r', 0.0)
                if radius > 0.001:
                    # Check X extent
                    arc_min_x = center_x - radius
                    arc_min_y = center_y - radius
                    if min_x is None or arc_min_x < min_x:
                        min_x = arc_min_x
                    if min_y is None or arc_min_y < min_y:
                        min_y = arc_min_y
            
            # Update previous point for next iteration
            prev_x = x
            prev_y = y
            prev_z = z
    
    # Check all drilling operations
    for op in operations:
        if op.get('type') == 'BohrVert':
            xa = op.get('xa', 0.0)
            ya = op.get('ya', 0.0)
            # Z is typically at surface (0) for drilling, but check depth
            depth = op.get('depth', 0.0)
            z = -depth  # Depth is negative Z
            
            if min_x is None or xa < min_x:
                min_x = xa
            if min_y is None or ya < min_y:
                min_y = ya
            if min_z is None or z < min_z:
                min_z = z
            points_checked += 1
    
    # Log calculation details
    print(f"[WoodWOP DEBUG] calculate_part_minimum(): checked {points_checked} points")
    print(f"[WoodWOP DEBUG]   Contours: {len(contours)}, Operations: {len(operations)}")
    
    # Return minimum coordinates or (0,0,0) if nothing found
    if min_x is None:
        print(f"[WoodWOP DEBUG]   No coordinates found, returning (0.0, 0.0, 0.0)")
        return (0.0, 0.0, 0.0)
    
    print(f"[WoodWOP DEBUG]   Minimum found: X={min_x:.3f}, Y={min_y:.3f}, Z={min_z:.3f}")
    return (min_x, min_y, min_z)


def generate_mpr_content():
    """Generate complete MPR format content and return as string.
    
    NOTE: If COORDINATE_SYSTEM is set (G54, G55, etc.), coordinates will be offset
    by the minimum part coordinates. This offset is applied ONLY to MPR format.
    G-code generation is NOT affected and remains unchanged.
    """
    global contours, operations, WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS
    global STOCK_EXTENT_X, STOCK_EXTENT_Y, OUTPUT_COMMENTS, PRECISION, now
    global COORDINATE_SYSTEM, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y, COORDINATE_OFFSET_Z
    
    output = []

    # Generate header
    header_lines = generate_mpr_header()
    output.extend(header_lines)
    
    # Generate contour elements
    elements_lines = generate_mpr_elements()
    output.extend(elements_lines)
    
    # Generate workpiece and variables section
    workpiece_lines = generate_mpr_workpiece()
    output.extend(workpiece_lines)
    
    # Generate operations
    operations_lines = generate_mpr_operations()
    output.extend(operations_lines)
    
    # End of file
    output.append('!')
    
    # Return the complete MPR content as a string
    return '\n'.join(output)


def generate_mpr_header():
    """Generate MPR file header section [H."""
    global WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS
    global STOCK_EXTENT_X, STOCK_EXTENT_Y
    
    output = []
    
    # Data head [H - All parameters from empty.mpr
    output.append('[H')
    output.append('VERSION="4.0 Alpha"')
    output.append('WW="9.0.152"')
    output.append('OP="1"')
    output.append('WRK2="0"')
    output.append('SCHN="0"')
    output.append('CVR="0"')
    output.append('POI="0"')
    output.append('HSP="0"')
    output.append('O2="0"')
    output.append('O4="0"')
    output.append('O3="0"')
    output.append('O5="0"')
    output.append('SR="0"')
    output.append('FM="1"')
    output.append('ML="2000"')
    output.append('UF="20"')
    output.append('ZS="20"')
    output.append('DN="STANDARD"')
    output.append('DST="0"')
    output.append('GP="0"')
    output.append('GY="0"')
    output.append('GXY="0"')
    output.append('NP="1"')
    output.append('NE="0"')
    output.append('NA="0"')
    output.append('BFS="0"')
    output.append('US="0"')
    output.append('CB="0"')
    output.append('UP="0"')
    output.append('DW="0"')
    output.append('MAT="HOMAG"')
    output.append('HP_A_O="STANDARD"')
    output.append('OVD_U="1"')
    output.append('OVD="0"')
    output.append('OHD_U="0"')
    output.append('OHD="2"')
    output.append('OOMD_U="0"')
    output.append('EWL="1"')
    output.append('INCH="0"')
    output.append('VIEW="NOMIRROR"')
    output.append('ANZ="1"')
    output.append('BES="0"')
    output.append('ENT="0"')
    output.append('MATERIAL=""')
    output.append('CUSTOMER=""')
    output.append('ORDER=""')
    output.append('ARTICLE=""')
    output.append('PARTID=""')
    output.append('PARTTYPE=""')
    output.append('MPRCOUNT="1"')
    output.append('MPRNUMBER="1"')
    output.append('INFO1=""')
    output.append('INFO2=""')
    output.append('INFO3=""')
    output.append('INFO4=""')
    output.append('INFO5=""')
    output.append(f'_BSX={WORKPIECE_LENGTH:.6f}')
    output.append(f'_BSY={WORKPIECE_WIDTH:.6f}')
    output.append(f'_BSZ={WORKPIECE_THICKNESS:.6f}')
    output.append(f'_FNX={STOCK_EXTENT_X:.6f}')
    output.append(f'_FNY={STOCK_EXTENT_Y:.6f}')
    output.append('_RNX=0.000000')
    output.append('_RNY=0.000000')
    output.append('_RNZ=0.000000')
    output.append(f'_RX={(WORKPIECE_LENGTH + 2 * STOCK_EXTENT_X):.6f}')
    output.append(f'_RY={(WORKPIECE_WIDTH + 2 * STOCK_EXTENT_Y):.6f}')
    output.append('')
    
    return output


def generate_mpr_elements():
    """Generate MPR contour elements section."""
    global contours, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y, COORDINATE_OFFSET_Z
    
    output = []
    
    # Contour elements (WoodWOP format)
    for contour in contours:
        output.append(f']{contour["id"]}')

        # Add starting point ($E0 KP) - always required for contours
        start_x, start_y, start_z = contour.get('start_pos', (0.0, 0.0, 0.0))
        
        # Apply coordinate offset if G54 or other coordinate system is set
        start_x += COORDINATE_OFFSET_X
        start_y += COORDINATE_OFFSET_Y
        start_z += COORDINATE_OFFSET_Z

        output.append('$E0')
        output.append('KP ')
        output.append(f'X={fmt(start_x)}')
        output.append(f'Y={fmt(start_y)}')
        output.append(f'Z={fmt(start_z)}')
        output.append('KO=00')
        output.append('.X=0.000000')
        output.append('.Y=0.000000')
        output.append('.Z=0.000000')
        output.append('.KO=00')
        output.append('')

        # Add contour elements
        # Track previous point coordinates (with offset applied) for angle calculations
        prev_elem_x = start_x
        prev_elem_y = start_y
        prev_elem_z = start_z
        
        for idx, elem in enumerate(contour['elements']):
            elem_num = idx + 1
            output.append(f'$E{elem_num}')

            if elem['type'] == 'KL':  # Line
                # Apply coordinate offset if G54 or other coordinate system is set
                elem_x = elem['x'] + COORDINATE_OFFSET_X
                elem_y = elem['y'] + COORDINATE_OFFSET_Y
                z_value = elem.get('z', 0.0) + COORDINATE_OFFSET_Z
                
                output.append('KL ')
                output.append(f'X={fmt(elem_x)}')
                output.append(f'Y={fmt(elem_y)}')
                # Z coordinate - always include (even if 0)
                output.append(f'Z={fmt(z_value)}')
                
                # Point values: absolute coordinates of end point relative to start point coordinate system
                # Calculate line angle in X/Y plane (WI) and angle to X/Y plane (WZ)
                # Use tracked previous point (already has offset applied)
                prev_x = prev_elem_x
                prev_y = prev_elem_y
                prev_z = prev_elem_z
                
                # Calculate line angles using helper function
                wi_angle, wz_angle = calculate_line_angles(prev_x, prev_y, prev_z, elem_x, elem_y, z_value)
                
                output.append(f'.X={fmt(elem_x)}')
                output.append(f'.Y={fmt(elem_y)}')
                output.append(f'.Z={fmt(z_value)}')
                output.append(f'.WI={fmt(wi_angle)}')
                output.append(f'.WZ={fmt(wz_angle)}')
                
                # Update tracked previous point for next element
                prev_elem_x = elem_x
                prev_elem_y = elem_y
                prev_elem_z = z_value

            elif elem['type'] == 'KA':  # Arc
                # Apply coordinate offset if G54 or other coordinate system is set
                elem_x = elem['x'] + COORDINATE_OFFSET_X
                elem_y = elem['y'] + COORDINATE_OFFSET_Y
                z_value = elem.get('z', 0.0) + COORDINATE_OFFSET_Z
                
                output.append('KA ')
                output.append(f'X={fmt(elem_x)}')  # End point X
                output.append(f'Y={fmt(elem_y)}')  # End point Y
                
                # Z coordinate - always include (even if 0) as shown in empty_3.mpr
                output.append(f'Z={fmt(z_value)}')

                # WoodWOP arc format: X, Y, Z (end point), DS (direction), R (radius)
                # Based on updated empty_3.mpr samples
                
                # Direction: 0=CW <=180, 1=CCW <=180, 2=CW >180, 3=CCW >180
                # Calculate DS based on direction and arc angle
                direction = elem.get('direction', 'CW')
                ds_value = 0
                if 'direction' in elem and 'r' in elem:
                    # For now, use simple direction mapping (WoodWOP will calculate exact value)
                    if direction == 'CCW':
                        ds_value = 1  # CCW <=180 (default)
                    else:
                        ds_value = 0  # CW <=180 (default)
                output.append(f'DS={ds_value}')

                # Radius - always include
                if 'r' in elem and elem['r'] > 0.001:
                    output.append(f'R={fmt(elem["r"])}')

                # Point values: absolute coordinates relative to start point coordinate system
                # Use tracked previous point (already has offset applied)
                prev_x = prev_elem_x
                prev_y = prev_elem_y
                prev_z = prev_elem_z
                
                # Calculate center coordinates (absolute) - I and J are offsets, so add to previous point
                center_x = prev_x + elem.get('i', 0)
                center_y = prev_y + elem.get('j', 0)
                
                # Calculate and normalize arc angles using helper function
                start_angle, end_angle = calculate_arc_angles(prev_x, prev_y, center_x, center_y, elem_x, elem_y, direction)
                
                # WAZ (angle to X/Y plane on arc path) - 0 for arcs in XY plane
                waz_angle = 0.0
                
                output.append(f'.X={fmt(elem_x)}')
                output.append(f'.Y={fmt(elem_y)}')
                output.append(f'.Z={fmt(z_value)}')
                output.append(f'.I={fmt(center_x)}')
                output.append(f'.J={fmt(center_y)}')
                output.append(f'.DS={ds_value}')
                output.append(f'.R={fmt(elem.get("r", 0.0))}')
                output.append(f'.WI={fmt(start_angle)}')
                output.append(f'.WO={fmt(end_angle)}')
                output.append(f'.WAZ={fmt(waz_angle)}')
                
                # Update tracked previous point for next element
                prev_elem_x = elem_x
                prev_elem_y = elem_y
                prev_elem_z = z_value

            output.append('')

        output.append('')
    
    return output


def generate_mpr_workpiece():
    """Generate MPR workpiece and variables section."""
    global WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS
    global STOCK_EXTENT_X, STOCK_EXTENT_Y, OUTPUT_COMMENTS, PRECISION, now
    global COORDINATE_SYSTEM, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y, COORDINATE_OFFSET_Z
    
    output = []
    
    # Variable section [001 (REQUIRED for WoodWOP) - always generate even if no contours
    output.append('[001')
    output.append(f'l="{fmt(WORKPIECE_LENGTH)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="Länge in X"')
    output.append(f'w="{fmt(WORKPIECE_WIDTH)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="Breite in Y"')
    output.append(f'th="{fmt(WORKPIECE_THICKNESS)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="Dicke in Z"')
    output.append('')

    # Workpiece definition
    output.append(f'<100 \\WerkStck\\')
    output.append(f'LA="l"')  # Use variable reference
    output.append(f'BR="w"')  # Use variable reference
    output.append(f'DI="th"')  # Use variable reference
    output.append(f'FNX="{fmt(STOCK_EXTENT_X)}"')  # Front Null X from stock
    output.append(f'FNY="{fmt(STOCK_EXTENT_Y)}"')  # Front Null Y from stock
    output.append(f'AX="0"')
    output.append(f'AY="0"')
    output.append('')

    # Comment
    if OUTPUT_COMMENTS:
        output.append('<101 \\Comment\\')
        output.append(f'KM="Generated by FreeCAD WoodWOP Post Processor"')
        output.append(f'KM="Date: {now.strftime("%Y-%m-%d %H:%M:%S")}"')
        if COORDINATE_SYSTEM:
            output.append(f'KM="Coordinate System: {COORDINATE_SYSTEM} (offset: X={COORDINATE_OFFSET_X:.3f}, Y={COORDINATE_OFFSET_Y:.3f}, Z={COORDINATE_OFFSET_Z:.3f})"')
            output.append(f'KM="NOTE: G-code output is NOT affected by coordinate system offset"')
        output.append('')
    
    return output


def generate_mpr_operations():
    """Generate MPR operations section."""
    global operations, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y
    
    output = []
    
    # Operations
    for op in operations:
        if op['type'] == 'BohrVert':
            # Apply coordinate offset if G54 or other coordinate system is set
            xa = op['xa'] + COORDINATE_OFFSET_X
            ya = op['ya'] + COORDINATE_OFFSET_Y
            
            output.append(f'<{op["id"]} \\BohrVert\\')
            output.append(f'XA="{fmt(xa)}"')
            output.append(f'YA="{fmt(ya)}"')
            output.append(f'TI="{fmt(op["depth"])}"')
            output.append(f'TNO="{op["tool"]}"')
            output.append(f'BM="SS"')
            output.append('')

        elif op['type'] == 'Contourfraesen':
            output.append(f'<{op["id"]} \\Contourfraesen\\')
            output.append(f'EA="{op["contour"]}:0"')
            output.append(f'MDA="TAN"')
            output.append(f'RK="WRKL"')
            output.append(f'EE="{op["contour"]}:1"')
            output.append(f'MDE="TAN_AB"')
            output.append(f'EM="1"')
            output.append(f'RI="1"')
            output.append(f'TNO="{op["tool"]}"')
            output.append(f'SM="0"')
            output.append('')

        elif op['type'] == 'Pocket':
            output.append(f'<{op["id"]} \\Pocket\\')
            output.append(f'EA="{op["contour"]}:0"')
            output.append(f'TNO="{op["tool"]}"')
            output.append('')
    
    return output


def calculate_line_angles(prev_x, prev_y, prev_z, elem_x, elem_y, z_value):
    """Calculate angles for a line element.
    
    Args:
        prev_x, prev_y, prev_z: Previous point coordinates
        elem_x, elem_y, z_value: Current point coordinates
    
    Returns:
        tuple: (wi_angle, wz_angle) - angles in radians
            wi_angle: Angle in X/Y plane
            wz_angle: Angle to X/Y plane
    """
    dx = elem_x - prev_x
    dy = elem_y - prev_y
    dz = z_value - prev_z
    
    # Calculate angle in X/Y plane (WI) - in radians
    if abs(dx) > 0.001 or abs(dy) > 0.001:
        wi_angle = math.atan2(dy, dx)
    else:
        wi_angle = 0.0
    
    # Calculate angle to X/Y plane (WZ) - in radians
    line_length_xy = math.sqrt(dx*dx + dy*dy)
    if line_length_xy > 0.001:
        wz_angle = math.atan2(dz, line_length_xy)
    else:
        wz_angle = 0.0
    
    return (wi_angle, wz_angle)


def calculate_arc_angles(prev_x, prev_y, center_x, center_y, elem_x, elem_y, direction):
    """Calculate and normalize angles for an arc element.
    
    Args:
        prev_x, prev_y: Previous point coordinates (arc start)
        center_x, center_y: Arc center coordinates
        elem_x, elem_y: Current point coordinates (arc end)
        direction: 'CW' or 'CCW'
    
    Returns:
        tuple: (start_angle, end_angle) - angles in radians (normalized)
    """
    # Calculate angles in X/Y plane
    start_angle = math.atan2(prev_y - center_y, prev_x - center_x)
    end_angle = math.atan2(elem_y - center_y, elem_x - center_x)
    
    # Normalize angles for direction
    if direction == 'CCW' and end_angle < start_angle:
        end_angle += 2 * math.pi
    elif direction == 'CW' and end_angle > start_angle:
        end_angle -= 2 * math.pi
    
    return (start_angle, end_angle)


def generate_mpr_content():
    """Generate complete MPR format content and return as string.
    
    NOTE: If COORDINATE_SYSTEM is set (G54, G55, etc.), coordinates will be offset
    by the minimum part coordinates. This offset is applied ONLY to MPR format.
    G-code generation is NOT affected and remains unchanged.
    """
    output = []

    # Generate header
    header_lines = generate_mpr_header()
    output.extend(header_lines)
    
    # Generate contour elements
    elements_lines = generate_mpr_elements()
    output.extend(elements_lines)
    
    # Generate workpiece and variables section
    workpiece_lines = generate_mpr_workpiece()
    output.extend(workpiece_lines)
    
    # Generate operations
    operations_lines = generate_mpr_operations()
    output.extend(operations_lines)
    
    # End of file
    output.append('!')
    
    # Return the complete MPR content as a string
    return '\n'.join(output)


def generate_mpr_header():
    """Generate MPR file header section [H."""
    global WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS
    global STOCK_EXTENT_X, STOCK_EXTENT_Y
    
    output = []
    
    # Data head [H - All parameters from empty.mpr
    output.append('[H')
    output.append('VERSION="4.0 Alpha"')
    output.append('WW="9.0.152"')
    output.append('OP="1"')
    output.append('WRK2="0"')
    output.append('SCHN="0"')
    output.append('CVR="0"')
    output.append('POI="0"')
    output.append('HSP="0"')
    output.append('O2="0"')
    output.append('O4="0"')
    output.append('O3="0"')
    output.append('O5="0"')
    output.append('SR="0"')
    output.append('FM="1"')
    output.append('ML="2000"')
    output.append('UF="20"')
    output.append('ZS="20"')
    output.append('DN="STANDARD"')
    output.append('DST="0"')
    output.append('GP="0"')
    output.append('GY="0"')
    output.append('GXY="0"')
    output.append('NP="1"')
    output.append('NE="0"')
    output.append('NA="0"')
    output.append('BFS="0"')
    output.append('US="0"')
    output.append('CB="0"')
    output.append('UP="0"')
    output.append('DW="0"')
    output.append('MAT="HOMAG"')
    output.append('HP_A_O="STANDARD"')
    output.append('OVD_U="1"')
    output.append('OVD="0"')
    output.append('OHD_U="0"')
    output.append('OHD="2"')
    output.append('OOMD_U="0"')
    output.append('EWL="1"')
    output.append('INCH="0"')
    output.append('VIEW="NOMIRROR"')
    output.append('ANZ="1"')
    output.append('BES="0"')
    output.append('ENT="0"')
    output.append('MATERIAL=""')
    output.append('CUSTOMER=""')
    output.append('ORDER=""')
    output.append('ARTICLE=""')
    output.append('PARTID=""')
    output.append('PARTTYPE=""')
    output.append('MPRCOUNT="1"')
    output.append('MPRNUMBER="1"')
    output.append('INFO1=""')
    output.append('INFO2=""')
    output.append('INFO3=""')
    output.append('INFO4=""')
    output.append('INFO5=""')
    output.append(f'_BSX={WORKPIECE_LENGTH:.6f}')
    output.append(f'_BSY={WORKPIECE_WIDTH:.6f}')
    output.append(f'_BSZ={WORKPIECE_THICKNESS:.6f}')
    output.append(f'_FNX={STOCK_EXTENT_X:.6f}')
    output.append(f'_FNY={STOCK_EXTENT_Y:.6f}')
    output.append('_RNX=0.000000')
    output.append('_RNY=0.000000')
    output.append('_RNZ=0.000000')
    output.append(f'_RX={(WORKPIECE_LENGTH + 2 * STOCK_EXTENT_X):.6f}')
    output.append(f'_RY={(WORKPIECE_WIDTH + 2 * STOCK_EXTENT_Y):.6f}')
    output.append('')
    
    return output




def generate_mpr_workpiece():
    """Generate MPR workpiece and variables section."""
    global WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS
    global STOCK_EXTENT_X, STOCK_EXTENT_Y, OUTPUT_COMMENTS, PRECISION, now
    global COORDINATE_SYSTEM, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y, COORDINATE_OFFSET_Z
    
    output = []
    
    # Variable section [001 (REQUIRED for WoodWOP) - always generate even if no contours
    output.append('[001')
    output.append(f'l="{fmt(WORKPIECE_LENGTH)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="Länge in X"')
    output.append(f'w="{fmt(WORKPIECE_WIDTH)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="Breite in Y"')
    output.append(f'th="{fmt(WORKPIECE_THICKNESS)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="Dicke in Z"')
    output.append('')

    # Workpiece definition
    output.append(f'<100 \\WerkStck\\')
    output.append(f'LA="l"')  # Use variable reference
    output.append(f'BR="w"')  # Use variable reference
    output.append(f'DI="th"')  # Use variable reference
    output.append(f'FNX="{fmt(STOCK_EXTENT_X)}"')  # Front Null X from stock
    output.append(f'FNY="{fmt(STOCK_EXTENT_Y)}"')  # Front Null Y from stock
    output.append(f'AX="0"')
    output.append(f'AY="0"')
    output.append('')

    # Comment
    if OUTPUT_COMMENTS:
        output.append('<101 \\Comment\\')
        output.append(f'KM="Generated by FreeCAD WoodWOP Post Processor"')
        output.append(f'KM="Date: {now.strftime("%Y-%m-%d %H:%M:%S")}"')
        if COORDINATE_SYSTEM:
            output.append(f'KM="Coordinate System: {COORDINATE_SYSTEM} (offset: X={COORDINATE_OFFSET_X:.3f}, Y={COORDINATE_OFFSET_Y:.3f}, Z={COORDINATE_OFFSET_Z:.3f})"')
            output.append(f'KM="NOTE: G-code output is NOT affected by coordinate system offset"')
        output.append('')
    
    return output


def generate_mpr_operations():
    """Generate MPR operations section."""
    global operations, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y
    
    output = []
    
    # Operations
    for op in operations:
        if op['type'] == 'BohrVert':
            # Apply coordinate offset if G54 or other coordinate system is set
            xa = op['xa'] + COORDINATE_OFFSET_X
            ya = op['ya'] + COORDINATE_OFFSET_Y
            
            output.append(f'<{op["id"]} \\BohrVert\\')
            output.append(f'XA="{fmt(xa)}"')
            output.append(f'YA="{fmt(ya)}"')
            output.append(f'TI="{fmt(op["depth"])}"')
            output.append(f'TNO="{op["tool"]}"')
            output.append(f'BM="SS"')
            output.append('')

        elif op['type'] == 'Contourfraesen':
            output.append(f'<{op["id"]} \\Contourfraesen\\')
            output.append(f'EA="{op["contour"]}:0"')
            output.append(f'MDA="TAN"')
            output.append(f'RK="WRKL"')
            output.append(f'EE="{op["contour"]}:1"')
            output.append(f'MDE="TAN_AB"')
            output.append(f'EM="1"')
            output.append(f'RI="1"')
            output.append(f'TNO="{op["tool"]}"')
            output.append(f'SM="0"')
            output.append('')

        elif op['type'] == 'Pocket':
            output.append(f'<{op["id"]} \\Pocket\\')
            output.append(f'EA="{op["contour"]}:0"')
            output.append(f'TNO="{op["tool"]}"')
            output.append('')
    
    return output


def fmt(value):
    """Format numeric value with precision."""
    return f"{value:.{PRECISION}f}"


def generate_gcode(objectslist):
    """Generate standard G-code from FreeCAD Path objects using parallel post processor.
    
    NOTE: This function does NOT apply coordinate system offsets (G54, G55, etc.).
    G-code coordinates remain unchanged regardless of COORDINATE_SYSTEM setting.
    Only MPR format applies coordinate offsets.
    """
    try:
        # Import the parallel G-code post processor
        import woodwop_gcode_post
        # Generate G-code using the dedicated post processor
        gcode_content = woodwop_gcode_post.export(objectslist, "-", "--no-show-editor --no-header")
        # Ensure we return a string, not bool or None
        if isinstance(gcode_content, bool):
            print(f"[WoodWOP WARNING] G-code post processor returned bool: {gcode_content}, using fallback")
            raise ValueError("G-code post processor returned bool instead of string")
        if not gcode_content or not isinstance(gcode_content, str):
            print(f"[WoodWOP WARNING] G-code post processor returned invalid type: {type(gcode_content)}, using fallback")
            raise ValueError(f"G-code post processor returned invalid type: {type(gcode_content)}")
        return gcode_content
    except Exception as e:
        print(f"[WoodWOP WARNING] Failed to use parallel G-code post processor: {e}")
        print(f"[WoodWOP WARNING] Falling back to simple G-code generation")
        
        # Fallback: simple G-code generation
        gcode_lines = []
        
        # Header
        gcode_lines.append("(Generated by FreeCAD WoodWOP Post Processor)")
        gcode_lines.append(f"(Date: {now.strftime('%Y-%m-%d %H:%M:%S')})")
        gcode_lines.append("")
        gcode_lines.append(UNITS)  # G21 for metric
        gcode_lines.append("G90")  # Absolute coordinates
        gcode_lines.append("G40")  # Cancel cutter compensation
        gcode_lines.append("")
        
        # Process all path objects
        for obj in objectslist:
            if not hasattr(obj, "Path"):
                continue
            
            # Add operation comment
            if OUTPUT_COMMENTS:
                gcode_lines.append(f"(Operation: {obj.Label if hasattr(obj, 'Label') else 'Unknown'})")
            
            # Process path commands
            for cmd in obj.Path.Commands:
                line = cmd.Name
                
                # Special handling for cutter compensation commands (G41/G42)
                if cmd.Name in ['G41', 'G41.1', 'G42', 'G42.1']:
                    # G41 - Left cutter radius compensation
                    # G41.1 - Dynamic left cutter radius compensation
                    # G42 - Right cutter radius compensation
                    # G42.1 - Dynamic right cutter radius compensation
                    
                    # Add D parameter (cutter compensation number)
                    if 'D' in cmd.Parameters:
                        # Use D parameter from command
                        line += f" D{int(cmd.Parameters['D'])}"
                    else:
                        # Use tool number as default D value
                        tool_number = get_tool_number(obj)
                        if tool_number:
                            line += f" D{tool_number}"
                    
                    # Add other parameters (X, Y, Z, I, J, etc.)
                    for param, value in sorted(cmd.Parameters.items()):
                        if param != 'D':  # D already added above
                            line += f" {param}{fmt(value)}"
                else:
                    # Regular command - add all parameters
                    for param, value in sorted(cmd.Parameters.items()):
                        line += f" {param}{fmt(value)}"
                
                gcode_lines.append(line)
            
            if OUTPUT_COMMENTS:
                gcode_lines.append("(End operation)")
                gcode_lines.append("")
        
        # Footer
        gcode_lines.append("M2")  # Program end
        gcode_lines.append("")
        
        return "\n".join(gcode_lines)


def linenumber():
    """Not used in MPR format."""
    return ''
