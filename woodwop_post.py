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
--report or /report: Enable job report generation
  When set, a detailed job report file (_job_report.txt) will be created.
  If not set, no report file will be generated.
--nc or /nc: Enable NC (G-code) file output
  When set, both MPR and NC files will be created.
  If not set, only MPR file will be created.
--p_c or /p_c or --p-c or /p-c: Enable Path Commands export
  When set, a detailed path commands file (_path_commands.txt) will be created.
  The file contains all Path Commands from all operations for debugging and analysis.
  If not set, no path commands file will be generated.
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
STOCK_EXTENT_X_NEG = 0.0  # l_off (left offset)
STOCK_EXTENT_X_POS = 0.0  # r_oz (right oversize)
STOCK_EXTENT_Y_NEG = 0.0  # f_off (front offset)
STOCK_EXTENT_Y_POS = 0.0  # b_oz (back oversize)
USE_PART_NAME = False

# Program offsets (for workpiece positioning in WoodWOP)
PROGRAM_OFFSET_X = 0.0
PROGRAM_OFFSET_Y = 0.0
PROGRAM_OFFSET_Z = 0.0

# Coordinate system offset (for G54, G55, etc.)
# If set, coordinates will be offset by the minimum part coordinates
# This is ONLY applied to MPR format, G-code remains unchanged
COORDINATE_SYSTEM = None  # None, 'G54', 'G55', 'G56', 'G57', 'G58', 'G59'
COORDINATE_OFFSET_X = 0.0
COORDINATE_OFFSET_Y = 0.0
COORDINATE_OFFSET_Z = 0.0

# Verbose logging flag
ENABLE_VERBOSE_LOGGING = False  # Set to True via /log or --log flag

# Job report flag
ENABLE_JOB_REPORT = False  # Set to True via /report or --report flag to enable job report generation

# NC file output flag
OUTPUT_NC_FILE = False  # Set to True via /nc or --nc flag to enable G-code output

# Path commands export flag
ENABLE_PATH_COMMANDS_EXPORT = False  # Set to True via /p_c or --p_c flag to enable path commands export

# Processing analysis export flag
ENABLE_PROCESSING_ANALYSIS = False  # Set to True via /p_a or --p_a flag to enable processing analysis export

# Z-safe minimum override flag
ENABLE_NO_Z_SAFE20 = False  # Set to True via /no_z_safe20 flag to disable 20mm minimum for z_safe

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
    global STOCK_EXTENT_X_NEG, STOCK_EXTENT_X_POS, STOCK_EXTENT_Y_NEG, STOCK_EXTENT_Y_POS
    global PROGRAM_OFFSET_X, PROGRAM_OFFSET_Y, PROGRAM_OFFSET_Z
    global contour_counter, contours, operations, tools_used
    global COORDINATE_SYSTEM, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y, COORDINATE_OFFSET_Z
    global ENABLE_VERBOSE_LOGGING, ENABLE_JOB_REPORT, OUTPUT_NC_FILE, ENABLE_PATH_COMMANDS_EXPORT, ENABLE_PROCESSING_ANALYSIS
    global ENABLE_NO_Z_SAFE20
    
    # Reset flags first
    ENABLE_VERBOSE_LOGGING = False
    ENABLE_JOB_REPORT = False
    OUTPUT_NC_FILE = False
    ENABLE_PATH_COMMANDS_EXPORT = False
    ENABLE_PROCESSING_ANALYSIS = False
    ENABLE_NO_Z_SAFE20 = False
    
    # Parse arguments FIRST to set flags before any other operations
    # This is critical for /log flag to work correctly with FilenameGenerator
    if argstring:
        print(f"[WoodWOP] Parsing arguments: '{argstring}'")
        args = argstring.split()
        print(f"[WoodWOP] Split into {len(args)} arguments: {args}")
        for arg in args:
            # Normalize argument to handle both -- and / formats
            normalized_arg = arg.lstrip('-').lstrip('/')
            print(f"[WoodWOP] Processing argument: '{arg}' (normalized: '{normalized_arg}')")
            
            if arg == '--log' or normalized_arg == 'log':
                ENABLE_VERBOSE_LOGGING = True
                print(f"[WoodWOP] Verbose logging enabled via {arg} flag")
                print(f"[WoodWOP] ENABLE_VERBOSE_LOGGING = True")
                # Update global variable
                import sys
                current_module = sys.modules.get(__name__)
                if current_module:
                    current_module.ENABLE_VERBOSE_LOGGING = True
            elif arg == '--report' or normalized_arg == 'report':
                ENABLE_JOB_REPORT = True
                print(f"[WoodWOP] Job report generation enabled via {arg} flag")
                print(f"[WoodWOP] ENABLE_JOB_REPORT = True")
                # Update global variable
                import sys
            elif arg in ['--no_z_safe20', '/no_z_safe20'] or normalized_arg == 'no_z_safe20':
                ENABLE_NO_Z_SAFE20 = True
                print(f"[WoodWOP] 20mm minimum for z_safe disabled via /no_z_safe20 flag")
                print(f"[WoodWOP] ENABLE_NO_Z_SAFE20 = True")
                current_module = sys.modules.get(__name__)
                if current_module:
                    current_module.ENABLE_JOB_REPORT = True
            elif arg == '--nc' or normalized_arg == 'nc':
                OUTPUT_NC_FILE = True
                print(f"[WoodWOP] NC file output enabled via {arg} flag")
                print(f"[WoodWOP] OUTPUT_NC_FILE = True")
                # Update global variable
                import sys
                current_module = sys.modules.get(__name__)
                if current_module:
                    current_module.OUTPUT_NC_FILE = True
                    print(f"[WoodWOP] Updated module.OUTPUT_NC_FILE = {current_module.OUTPUT_NC_FILE}")
            elif arg in ['--p_c', '--p-c'] or normalized_arg in ['p_c', 'p-c']:
                ENABLE_PATH_COMMANDS_EXPORT = True
                print(f"[WoodWOP] Path commands export enabled via {arg} flag")
                print(f"[WoodWOP] ENABLE_PATH_COMMANDS_EXPORT = True")
                # Update global variable
                import sys
                current_module = sys.modules.get(__name__)
                if current_module:
                    current_module.ENABLE_PATH_COMMANDS_EXPORT = True
                    print(f"[WoodWOP] Updated module.ENABLE_PATH_COMMANDS_EXPORT = {current_module.ENABLE_PATH_COMMANDS_EXPORT}")
            elif arg in ['--p_a', '--p-a'] or normalized_arg in ['p_a', 'p-a']:
                ENABLE_PROCESSING_ANALYSIS = True
                print(f"[WoodWOP] Processing analysis export enabled via {arg} flag")
                print(f"[WoodWOP] ENABLE_PROCESSING_ANALYSIS = True")
                # Update global variable
                import sys
                current_module = sys.modules.get(__name__)
                if current_module:
                    current_module.ENABLE_PROCESSING_ANALYSIS = True
                    print(f"[WoodWOP] Updated module.ENABLE_PROCESSING_ANALYSIS = {current_module.ENABLE_PROCESSING_ANALYSIS}")
    
    # Debug output - use both print() and FreeCAD.Console to ensure visibility
    debug_log("[WoodWOP DEBUG] ===== export() called =====")
    debug_log(f"[WoodWOP DEBUG] File: {__file__}")
    debug_log(f"[WoodWOP DEBUG] objectslist type: {type(objectslist)}, length: {len(objectslist) if hasattr(objectslist, '__len__') else 'N/A'}")
    debug_log(f"[WoodWOP DEBUG] filename: {filename}")
    debug_log(f"[WoodWOP DEBUG] argstring: '{argstring}'")
    print(f"[WoodWOP] argstring received: '{argstring}'")
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

    # Continue parsing remaining arguments (non-flag arguments)
    if argstring:
        args = argstring.split()
        for arg in args:
            # Normalize argument to handle both -- and / formats
            normalized_arg = arg.lstrip('-').lstrip('/')
            
            if arg == '--no-comments' or normalized_arg == 'no-comments':
                OUTPUT_COMMENTS = False
                print(f"[WoodWOP] OUTPUT_COMMENTS = False")
            elif arg == '--use-part-name' or normalized_arg == 'use-part-name':
                USE_PART_NAME = True
                print(f"[WoodWOP] USE_PART_NAME = True")
            elif arg.startswith('--precision=') or normalized_arg.startswith('precision='):
                value = arg.split('=')[1] if '=' in arg else normalized_arg.split('=')[1]
                PRECISION = int(value)
                print(f"[WoodWOP] PRECISION = {PRECISION}")
            elif arg.startswith('--workpiece-length=') or normalized_arg.startswith('workpiece-length='):
                value = arg.split('=')[1] if '=' in arg else normalized_arg.split('=')[1]
                WORKPIECE_LENGTH = float(value)
                print(f"[WoodWOP] WORKPIECE_LENGTH = {WORKPIECE_LENGTH}")
            elif arg.startswith('--workpiece-width=') or normalized_arg.startswith('workpiece-width='):
                value = arg.split('=')[1] if '=' in arg else normalized_arg.split('=')[1]
                WORKPIECE_WIDTH = float(value)
                print(f"[WoodWOP] WORKPIECE_WIDTH = {WORKPIECE_WIDTH}")
            elif arg.startswith('--workpiece-thickness=') or normalized_arg.startswith('workpiece-thickness='):
                value = arg.split('=')[1] if '=' in arg else normalized_arg.split('=')[1]
                WORKPIECE_THICKNESS = float(value)
                print(f"[WoodWOP] WORKPIECE_THICKNESS = {WORKPIECE_THICKNESS}")
            elif arg in ['--g54', '--G54'] or normalized_arg.lower() == 'g54':
                # Legacy flag support - will be overridden by Job.Fixtures if present
                COORDINATE_SYSTEM = 'G54'
                print(f"[WoodWOP] COORDINATE_SYSTEM = G54 (via {arg} flag)")
                debug_log(f"[WoodWOP DEBUG] Coordinate system set to G54 via {arg} flag (legacy mode)")
    
    # Debug: Print final flag values
    print(f"[WoodWOP] Final flag values after parsing:")
    print(f"[WoodWOP]   OUTPUT_NC_FILE = {OUTPUT_NC_FILE}")
    print(f"[WoodWOP]   ENABLE_VERBOSE_LOGGING = {ENABLE_VERBOSE_LOGGING}")
    print(f"[WoodWOP]   ENABLE_JOB_REPORT = {ENABLE_JOB_REPORT}")
    print(f"[WoodWOP]   ENABLE_PATH_COMMANDS_EXPORT = {ENABLE_PATH_COMMANDS_EXPORT}")

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
    if OUTPUT_NC_FILE:
        print(f"[WoodWOP DEBUG] Will create: {os.path.join(output_dir, base_filename + '.mpr')} and {os.path.join(output_dir, base_filename + '.nc')}")
    else:
        print(f"[WoodWOP DEBUG] Will create: {os.path.join(output_dir, base_filename + '.mpr')} (NC file disabled)")

    # Auto-detect workpiece dimensions if not specified
    # Priority: 1) Arguments, 2) Stock dimensions (Job.Stock), 3) Model dimensions (Job.Model), 4) Base dimensions (Job.Base), 5) Defaults
    
    # First priority: Stock dimensions (most accurate for workpiece)
    if job and hasattr(job, 'Stock') and job.Stock:
        stock = job.Stock
        try:
            if WORKPIECE_LENGTH is None and hasattr(stock, 'Length'):
                WORKPIECE_LENGTH = stock.Length.Value if hasattr(stock.Length, 'Value') else stock.Length
                print(f"[WoodWOP DEBUG] Detected workpiece length from Stock: {WORKPIECE_LENGTH:.3f} mm")
            if WORKPIECE_WIDTH is None and hasattr(stock, 'Width'):
                WORKPIECE_WIDTH = stock.Width.Value if hasattr(stock.Width, 'Value') else stock.Width
                print(f"[WoodWOP DEBUG] Detected workpiece width from Stock: {WORKPIECE_WIDTH:.3f} mm")
            if WORKPIECE_THICKNESS is None and hasattr(stock, 'Height'):
                WORKPIECE_THICKNESS = stock.Height.Value if hasattr(stock.Height, 'Value') else stock.Height
                print(f"[WoodWOP DEBUG] Detected workpiece thickness from Stock: {WORKPIECE_THICKNESS:.3f} mm")

            # Get stock extents (oversizes) for raw material calculations
            # According to WoodWOP standard, we need separate variables:
            # l_off (left offset = ExtentXNeg), f_off (front offset = ExtentYNeg)
            # r_oz (right oversize = ExtentXPos), b_oz (back oversize = ExtentYPos)
            stock_extent_x_neg = 0.0  # l_off
            stock_extent_x_pos = 0.0  # r_oz
            stock_extent_y_neg = 0.0  # f_off
            stock_extent_y_pos = 0.0  # b_oz
            
            if hasattr(stock, 'ExtentXNeg'):
                stock_extent_x_neg = stock.ExtentXNeg.Value if hasattr(stock.ExtentXNeg, 'Value') else stock.ExtentXNeg
            elif hasattr(stock, 'ExtXneg'):
                stock_extent_x_neg = stock.ExtXneg.Value if hasattr(stock.ExtXneg, 'Value') else stock.ExtXneg
            
            if hasattr(stock, 'ExtentXPos'):
                stock_extent_x_pos = stock.ExtentXPos.Value if hasattr(stock.ExtentXPos, 'Value') else stock.ExtentXPos
            elif hasattr(stock, 'ExtXpos'):
                stock_extent_x_pos = stock.ExtXpos.Value if hasattr(stock.ExtXpos, 'Value') else stock.ExtXpos
            
            if hasattr(stock, 'ExtentYNeg'):
                stock_extent_y_neg = stock.ExtentYNeg.Value if hasattr(stock.ExtentYNeg, 'Value') else stock.ExtentYNeg
            elif hasattr(stock, 'ExtYneg'):
                stock_extent_y_neg = stock.ExtYneg.Value if hasattr(stock.ExtYneg, 'Value') else stock.ExtYneg
            
            if hasattr(stock, 'ExtentYPos'):
                stock_extent_y_pos = stock.ExtentYPos.Value if hasattr(stock.ExtentYPos, 'Value') else stock.ExtentYPos
            elif hasattr(stock, 'ExtYpos'):
                stock_extent_y_pos = stock.ExtYpos.Value if hasattr(stock.ExtYpos, 'Value') else stock.ExtYpos
            
            # Store individual extents for MPR variables
            # STOCK_EXTENT_X and STOCK_EXTENT_Y are kept for backward compatibility
            STOCK_EXTENT_X = stock_extent_x_neg + stock_extent_x_pos
            STOCK_EXTENT_Y = stock_extent_y_neg + stock_extent_y_pos
            
            # Store individual values for MPR variables
            global STOCK_EXTENT_X_NEG, STOCK_EXTENT_X_POS, STOCK_EXTENT_Y_NEG, STOCK_EXTENT_Y_POS
            STOCK_EXTENT_X_NEG = stock_extent_x_neg
            STOCK_EXTENT_X_POS = stock_extent_x_pos
            STOCK_EXTENT_Y_NEG = stock_extent_y_neg
            STOCK_EXTENT_Y_POS = stock_extent_y_pos
            
            print(f"[WoodWOP DEBUG] Stock extents: l_off (X-)={stock_extent_x_neg:.3f}, r_oz (X+)={stock_extent_x_pos:.3f}, f_off (Y-)={stock_extent_y_neg:.3f}, b_oz (Y+)={stock_extent_y_pos:.3f}")
            print(f"[WoodWOP DEBUG] Stock extents total: FNX={STOCK_EXTENT_X:.3f}, FNY={STOCK_EXTENT_Y:.3f}")
            
            # Get program offsets (x, y, z) if available
            if hasattr(stock, 'Position') and stock.Position:
                pos = stock.Position
                if hasattr(pos, 'x'):
                    PROGRAM_OFFSET_X = pos.x.Value if hasattr(pos.x, 'Value') else pos.x
                elif hasattr(pos, 'X'):
                    PROGRAM_OFFSET_X = pos.X.Value if hasattr(pos.X, 'Value') else pos.X
                if hasattr(pos, 'y'):
                    PROGRAM_OFFSET_Y = pos.y.Value if hasattr(pos.y, 'Value') else pos.y
                elif hasattr(pos, 'Y'):
                    PROGRAM_OFFSET_Y = pos.Y.Value if hasattr(pos.Y, 'Value') else pos.Y
                if hasattr(pos, 'z'):
                    PROGRAM_OFFSET_Z = pos.z.Value if hasattr(pos.z, 'Value') else pos.z
                elif hasattr(pos, 'Z'):
                    PROGRAM_OFFSET_Z = pos.Z.Value if hasattr(pos.Z, 'Value') else pos.Z
                print(f"[WoodWOP DEBUG] Program offsets from Stock.Position: x={PROGRAM_OFFSET_X:.3f}, y={PROGRAM_OFFSET_Y:.3f}, z={PROGRAM_OFFSET_Z:.3f}")
            elif hasattr(stock, 'ProgramOffset'):
                prog_offset = stock.ProgramOffset
                if hasattr(prog_offset, 'x'):
                    PROGRAM_OFFSET_X = prog_offset.x.Value if hasattr(prog_offset.x, 'Value') else prog_offset.x
                elif hasattr(prog_offset, 'X'):
                    PROGRAM_OFFSET_X = prog_offset.X.Value if hasattr(prog_offset.X, 'Value') else prog_offset.X
                if hasattr(prog_offset, 'y'):
                    PROGRAM_OFFSET_Y = prog_offset.y.Value if hasattr(prog_offset.y, 'Value') else prog_offset.y
                elif hasattr(prog_offset, 'Y'):
                    PROGRAM_OFFSET_Y = prog_offset.Y.Value if hasattr(prog_offset.Y, 'Value') else prog_offset.Y
                if hasattr(prog_offset, 'z'):
                    PROGRAM_OFFSET_Z = prog_offset.z.Value if hasattr(prog_offset.z, 'Value') else prog_offset.z
                elif hasattr(prog_offset, 'Z'):
                    PROGRAM_OFFSET_Z = prog_offset.Z.Value if hasattr(prog_offset.Z, 'Value') else prog_offset.Z
                print(f"[WoodWOP DEBUG] Program offsets from Stock.ProgramOffset: x={PROGRAM_OFFSET_X:.3f}, y={PROGRAM_OFFSET_Y:.3f}, z={PROGRAM_OFFSET_Z:.3f}")
        except Exception as e:
            print(f"[WoodWOP DEBUG] Could not get dimensions from Stock: {e}")
    
    # Second priority: Model dimensions
    if job and (WORKPIECE_LENGTH is None or WORKPIECE_WIDTH is None or WORKPIECE_THICKNESS is None):
        if hasattr(job, 'Model') and job.Model:
            try:
                model_obj = job.Model
                if hasattr(model_obj, 'Shape') and hasattr(model_obj.Shape, 'BoundBox'):
                    bbox = model_obj.Shape.BoundBox
                    if WORKPIECE_LENGTH is None:
                        WORKPIECE_LENGTH = bbox.XLength
                        print(f"[WoodWOP DEBUG] Detected workpiece length from Model: {WORKPIECE_LENGTH:.3f} mm")
                    if WORKPIECE_WIDTH is None:
                        WORKPIECE_WIDTH = bbox.YLength
                        print(f"[WoodWOP DEBUG] Detected workpiece width from Model: {WORKPIECE_WIDTH:.3f} mm")
                    if WORKPIECE_THICKNESS is None:
                        WORKPIECE_THICKNESS = bbox.ZLength
                        print(f"[WoodWOP DEBUG] Detected workpiece thickness from Model: {WORKPIECE_THICKNESS:.3f} mm")
            except Exception as e:
                print(f"[WoodWOP DEBUG] Could not get dimensions from Model: {e}")
    
    # Third priority: Base dimensions
    if job and (WORKPIECE_LENGTH is None or WORKPIECE_WIDTH is None or WORKPIECE_THICKNESS is None):
        if hasattr(job, 'Base') and job.Base:
            try:
                base_obj = None
                if isinstance(job.Base, (list, tuple)) and len(job.Base) > 0:
                    base_obj = job.Base[0]
                elif hasattr(job.Base, 'Shape'):
                    base_obj = job.Base
                elif hasattr(job.Base, 'Name'):
                    try:
                        import FreeCAD
                        doc = FreeCAD.ActiveDocument
                        if doc:
                            base_obj = doc.getObject(job.Base.Name)
                    except:
                        pass
                
                if base_obj and hasattr(base_obj, 'Shape') and hasattr(base_obj.Shape, 'BoundBox'):
                    bbox = base_obj.Shape.BoundBox
                    if WORKPIECE_LENGTH is None:
                        WORKPIECE_LENGTH = bbox.XLength
                        print(f"[WoodWOP DEBUG] Detected workpiece length from Base: {WORKPIECE_LENGTH:.3f} mm")
                    if WORKPIECE_WIDTH is None:
                        WORKPIECE_WIDTH = bbox.YLength
                        print(f"[WoodWOP DEBUG] Detected workpiece width from Base: {WORKPIECE_WIDTH:.3f} mm")
                    if WORKPIECE_THICKNESS is None:
                        WORKPIECE_THICKNESS = bbox.ZLength
                        print(f"[WoodWOP DEBUG] Detected workpiece thickness from Base: {WORKPIECE_THICKNESS:.3f} mm")
            except Exception as e:
                print(f"[WoodWOP DEBUG] Could not get dimensions from Base: {e}")

    # Set defaults if still None
    if WORKPIECE_LENGTH is None:
        WORKPIECE_LENGTH = 800.0
        print(f"[WoodWOP DEBUG] Using default workpiece length: {WORKPIECE_LENGTH:.3f} mm")
    if WORKPIECE_WIDTH is None:
        WORKPIECE_WIDTH = 600.0
        print(f"[WoodWOP DEBUG] Using default workpiece width: {WORKPIECE_WIDTH:.3f} mm")
    if WORKPIECE_THICKNESS is None:
        WORKPIECE_THICKNESS = 20.0
        print(f"[WoodWOP DEBUG] Using default workpiece thickness: {WORKPIECE_THICKNESS:.3f} mm")
    
    print(f"[WoodWOP DEBUG] Final workpiece dimensions: L={WORKPIECE_LENGTH:.3f} x W={WORKPIECE_WIDTH:.3f} x T={WORKPIECE_THICKNESS:.3f} mm")

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
    # Priority: 1) Job.Model bounding box, 2) Job.Base bounding box, 3) Contours (fallback)
    if COORDINATE_SYSTEM:
        min_x = None
        min_y = None
        min_z = None
        
        # Try to get from Job.Model first (most accurate)
        if job and hasattr(job, 'Model') and job.Model:
            try:
                model_obj = job.Model
                if hasattr(model_obj, 'Shape') and hasattr(model_obj.Shape, 'BoundBox'):
                    bbox = model_obj.Shape.BoundBox
                    min_x = bbox.XMin
                    min_y = bbox.YMin
                    min_z = bbox.ZMin
                    print(f"[WoodWOP DEBUG] G54 offset from Job.Model.BoundBox: X={min_x:.3f}, Y={min_y:.3f}, Z={min_z:.3f}")
                elif hasattr(model_obj, 'BoundBox'):
                    bbox = model_obj.BoundBox
                    min_x = bbox.XMin
                    min_y = bbox.YMin
                    min_z = bbox.ZMin
                    print(f"[WoodWOP DEBUG] G54 offset from Job.Model.BoundBox: X={min_x:.3f}, Y={min_y:.3f}, Z={min_z:.3f}")
            except Exception as e:
                print(f"[WoodWOP DEBUG] Could not get G54 offset from Job.Model: {e}")
        
        # If Model not available, try Base
        if min_x is None and job and hasattr(job, 'Base') and job.Base:
            try:
                base_obj = None
                if isinstance(job.Base, (list, tuple)) and len(job.Base) > 0:
                    base_obj = job.Base[0]
                elif hasattr(job.Base, 'Shape'):
                    base_obj = job.Base
                elif hasattr(job.Base, 'Name'):
                    try:
                        import FreeCAD
                        doc = FreeCAD.ActiveDocument
                        if doc:
                            base_obj = doc.getObject(job.Base.Name)
                    except:
                        pass
                
                if base_obj and hasattr(base_obj, 'Shape') and hasattr(base_obj.Shape, 'BoundBox'):
                    bbox = base_obj.Shape.BoundBox
                    min_x = bbox.XMin
                    min_y = bbox.YMin
                    min_z = bbox.ZMin
                    print(f"[WoodWOP DEBUG] G54 offset from Job.Base.BoundBox: X={min_x:.3f}, Y={min_y:.3f}, Z={min_z:.3f}")
            except Exception as e:
                print(f"[WoodWOP DEBUG] Could not get G54 offset from Job.Base: {e}")
        
        # Fallback: calculate from contours (less accurate)
        if min_x is None:
            min_x, min_y, min_z = calculate_part_minimum()
            print(f"[WoodWOP DEBUG] G54 offset from contours (fallback): X={min_x:.3f}, Y={min_y:.3f}, Z={min_z:.3f}")
            print(f"[WoodWOP WARNING] Using contour-based G54 offset - may be inaccurate! Use Job.Model for accurate offset.")
        
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
    
    # Calculate z_safe from SetupSheet.ClearanceHeightOffset
    z_safe = 20.0  # Default value
    z_safe_actual = None
    z_safe_was_increased = False
    
    if job:
        try:
            # Try to get SetupSheet from Job
            setup_sheet = None
            if hasattr(job, 'SetupSheet') and job.SetupSheet:
                setup_sheet = job.SetupSheet
            elif hasattr(job, 'SetupSheetName') and job.SetupSheetName:
                try:
                    import FreeCAD
                    doc = FreeCAD.ActiveDocument
                    if doc:
                        setup_sheet = doc.getObject(job.SetupSheetName)
                except:
                    pass
            
            if setup_sheet:
                # Get ClearanceHeightOffset from SetupSheet
                if hasattr(setup_sheet, 'ClearanceHeightOffset'):
                    clearance_height = setup_sheet.ClearanceHeightOffset
                    if hasattr(clearance_height, 'Value'):
                        z_safe_actual = float(clearance_height.Value)
                    else:
                        z_safe_actual = float(clearance_height)
                    print(f"[WoodWOP DEBUG] Found ClearanceHeightOffset in SetupSheet: {z_safe_actual:.3f} mm")
                else:
                    print(f"[WoodWOP DEBUG] SetupSheet has no ClearanceHeightOffset property")
            else:
                print(f"[WoodWOP DEBUG] No SetupSheet found in Job")
        except Exception as e:
            print(f"[WoodWOP DEBUG] Could not get z_safe from SetupSheet: {e}")
    
    # Apply minimum 20mm if flag is not set
    if z_safe_actual is not None:
        z_safe = z_safe_actual
        if not ENABLE_NO_Z_SAFE20 and z_safe < 20.0:
            z_safe = 20.0
            z_safe_was_increased = True
            print(f"[WoodWOP DEBUG] z_safe increased from {z_safe_actual:.3f} to 20.0 mm (minimum)")
    else:
        print(f"[WoodWOP DEBUG] Using default z_safe: {z_safe:.3f} mm")
    
    # Show pop-up window with z_safe information
    try:
        import FreeCAD
        import FreeCADGui
        
        if z_safe_was_increased:
            # Red message: actual value was less than 20mm but 20mm was used
            message = f"z_safe увеличен до минимума 20 мм\n\nФактическое значение ClearanceHeightOffset: {z_safe_actual:.3f} мм\nИспользуемое значение: {z_safe:.3f} мм\n\nИспользуйте флаг /no_z_safe20 для отключения минимума."
            FreeCADGui.showDialog("WoodWOP Warning", message, severity="error")
            print(f"[WoodWOP WARNING] z_safe was increased to minimum 20mm (actual: {z_safe_actual:.3f} mm)")
        elif z_safe_actual is not None and z_safe_actual > 20.0:
            # Yellow message: value is greater than 20mm
            message = f"z_safe значение больше 20 мм\n\nClearanceHeightOffset: {z_safe_actual:.3f} мм\nИспользуемое значение: {z_safe:.3f} мм"
            FreeCADGui.showDialog("WoodWOP Info", message, severity="warning")
            print(f"[WoodWOP INFO] z_safe is {z_safe:.3f} mm (greater than 20mm)")
    except Exception as e:
        print(f"[WoodWOP DEBUG] Could not show z_safe dialog: {e}")
    
    mpr_content = generate_mpr_content(z_safe)
    # Validate MPR content
    if not isinstance(mpr_content, str):
        print(f"[WoodWOP ERROR] generate_mpr_content() returned {type(mpr_content)} instead of string: {mpr_content}")
        raise ValueError(f"generate_mpr_content() returned {type(mpr_content)} instead of string")
    print(f"[WoodWOP DEBUG] Generated {len(mpr_content)} characters")
    print(f"[WoodWOP DEBUG] First 500 chars of MPR: {mpr_content[:500]}")
    
    # CRITICAL: Check if mpr_content is empty
    if len(mpr_content) == 0:
        error_msg = "[WoodWOP CRITICAL ERROR] mpr_content is EMPTY! File will be empty!"
        print(error_msg)
        try:
            import FreeCAD
            FreeCAD.Console.PrintError(f"{error_msg}\n")
        except:
            pass
    
    # Generate G-code content only if /nc flag is set
    print(f"[WoodWOP] Checking OUTPUT_NC_FILE before generating G-code: {OUTPUT_NC_FILE}")
    gcode_content = ""
    if OUTPUT_NC_FILE:
        print(f"[WoodWOP] Generating G-code content (NC output enabled)...")
        gcode_content = generate_gcode(objectslist)
        # Validate G-code content
        if not isinstance(gcode_content, str):
            print(f"[WoodWOP ERROR] generate_gcode() returned {type(gcode_content)} instead of string: {gcode_content}")
            raise ValueError(f"generate_gcode() returned {type(gcode_content)} instead of string")
        print(f"[WoodWOP] Generated {len(gcode_content)} characters of G-code")
    else:
        print(f"[WoodWOP] NC file output disabled (OUTPUT_NC_FILE = {OUTPUT_NC_FILE}, use /nc flag to enable)")

    # NOTE: DO NOT create files here - let FreeCAD handle file creation based on returned list
    # Report creation is moved to Command.py to ensure it happens AFTER user confirms filename in dialog
    
    # Return list of tuples: [(subpart_name, content), ...]
    # FreeCAD will create separate files for each tuple
    # Format: [("mpr", mpr_content)] or [("mpr", mpr_content), ("nc", gcode_content)]
    # FreeCAD will use subpart_name to determine file extension
    if OUTPUT_NC_FILE:
        print(f"[WoodWOP DEBUG] Returning both MPR and NC formats to FreeCAD")
        print(f"[WoodWOP DEBUG] MPR content type: {type(mpr_content)}, length: {len(mpr_content)} characters")
        print(f"[WoodWOP DEBUG] G-code content type: {type(gcode_content)}, length: {len(gcode_content)} characters")
    else:
        print(f"[WoodWOP DEBUG] Returning only MPR format to FreeCAD")
        print(f"[WoodWOP DEBUG] MPR content type: {type(mpr_content)}, length: {len(mpr_content)} characters")
    
    # CRITICAL: Ensure mpr_content is a string before building result
    if not isinstance(mpr_content, str):
        error_msg = f"[WoodWOP CRITICAL ERROR] mpr_content is not a string! Type: {type(mpr_content)}"
        print(error_msg)
        try:
            import FreeCAD
            FreeCAD.Console.PrintError(f"{error_msg}\n")
        except:
            pass
        # Convert to string
        mpr_content = str(mpr_content) if mpr_content else ""
        print(f"[WoodWOP DEBUG] Converted mpr_content to string, new length: {len(mpr_content)}")
    
    # CRITICAL: Build result list and verify it's correct
    # Include NC file only if OUTPUT_NC_FILE flag is set
    print(f"[WoodWOP] Building result list, OUTPUT_NC_FILE = {OUTPUT_NC_FILE}")
    print(f"[WoodWOP DEBUG] mpr_content type: {type(mpr_content)}, length: {len(mpr_content) if mpr_content else 0}")
    
    # CRITICAL: Verify mpr_content is not empty
    if len(mpr_content) == 0:
        error_msg = "[WoodWOP CRITICAL ERROR] mpr_content is EMPTY before building result!"
        print(error_msg)
        try:
            import FreeCAD
            FreeCAD.Console.PrintError(f"{error_msg}\n")
        except:
            pass
    
    if OUTPUT_NC_FILE:
        result = [("mpr", str(mpr_content)), ("nc", str(gcode_content) if gcode_content else "")]
        print(f"[WoodWOP] Result list will contain 2 items: MPR and NC")
        print(f"[WoodWOP DEBUG] MPR content length: {len(mpr_content) if mpr_content else 0}, NC content length: {len(gcode_content) if gcode_content else 0}")
    else:
        result = [("mpr", str(mpr_content))]
        print(f"[WoodWOP] Result list will contain 1 item: MPR only")
        print(f"[WoodWOP DEBUG] MPR content length: {len(mpr_content) if mpr_content else 0}")
        print(f"[WoodWOP DEBUG] Result tuple content type: {type(result[0][1])}, length: {len(result[0][1]) if result[0][1] else 0}")
    
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
        if OUTPUT_NC_FILE:
            result = [("mpr", str(mpr_content) if mpr_content else ""), ("nc", str(gcode_content) if gcode_content else "")]
        else:
            result = [("mpr", str(mpr_content) if mpr_content else "")]
    
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
        if OUTPUT_NC_FILE:
            return [("mpr", ""), ("nc", "")]
        else:
            return [("mpr", "")]
    
    return result


def create_job_report(job, report_filename):
    """Create a detailed report of all Job properties."""
    import datetime
    global WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS
    global COORDINATE_SYSTEM, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y, COORDINATE_OFFSET_Z
    
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
    stock_extent_x_neg = 0.0
    stock_extent_x_pos = 0.0
    stock_extent_y_neg = 0.0
    stock_extent_y_pos = 0.0
    stock_extent_z_neg = 0.0
    stock_extent_z_pos = 0.0
    
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
        
        # Extract stock extents (oversizes) in all directions
        if hasattr(stock, 'ExtentXNeg') or hasattr(stock, 'ExtXneg'):
            stock_extent_x_neg = getattr(stock, 'ExtentXNeg', getattr(stock, 'ExtXneg', None))
        if hasattr(stock, 'ExtentXPos') or hasattr(stock, 'ExtXpos'):
            stock_extent_x_pos = getattr(stock, 'ExtentXPos', getattr(stock, 'ExtXpos', None))
        if hasattr(stock, 'ExtentYNeg') or hasattr(stock, 'ExtYneg'):
            stock_extent_y_neg = getattr(stock, 'ExtentYNeg', getattr(stock, 'ExtYneg', None))
        if hasattr(stock, 'ExtentYPos') or hasattr(stock, 'ExtYpos'):
            stock_extent_y_pos = getattr(stock, 'ExtentYPos', getattr(stock, 'ExtYpos', None))
        if hasattr(stock, 'ExtentZNeg') or hasattr(stock, 'ExtZneg'):
            stock_extent_z_neg = getattr(stock, 'ExtentZNeg', getattr(stock, 'ExtZneg', None))
        if hasattr(stock, 'ExtentZPos') or hasattr(stock, 'ExtZpos'):
            stock_extent_z_pos = getattr(stock, 'ExtentZPos', getattr(stock, 'ExtZpos', None))
    
    report_lines.append("")
    
    # Extract float values from Quantity objects if needed
    def get_float_value(value):
        """Extract float value from Quantity object or return as-is if already float."""
        if value is None:
            return 0.0
        if hasattr(value, 'Value'):
            # If Value itself is a Quantity, recurse
            val = value.Value
            if hasattr(val, 'Value'):
                return get_float_value(val)
            return float(val)
        return float(value)
    
    # Convert all values to float before formatting
    workpiece_length_val = get_float_value(WORKPIECE_LENGTH)
    workpiece_width_val = get_float_value(WORKPIECE_WIDTH)
    workpiece_thickness_val = get_float_value(WORKPIECE_THICKNESS)
    
    # Convert stock extents to float
    stock_extent_x_neg = get_float_value(stock_extent_x_neg)
    stock_extent_x_pos = get_float_value(stock_extent_x_pos)
    stock_extent_y_neg = get_float_value(stock_extent_y_neg)
    stock_extent_y_pos = get_float_value(stock_extent_y_pos)
    stock_extent_z_neg = get_float_value(stock_extent_z_neg)
    stock_extent_z_pos = get_float_value(stock_extent_z_pos)
    
    # Workpiece dimensions and oversizes section
    report_lines.append("-" * 80)
    report_lines.append("WORKPIECE DIMENSIONS AND OVERSIZES")
    report_lines.append("-" * 80)
    report_lines.append(f"Workpiece Length (X): {workpiece_length_val:.3f} mm")
    report_lines.append(f"Workpiece Width (Y):  {workpiece_width_val:.3f} mm")
    report_lines.append(f"Workpiece Thickness (Z): {workpiece_thickness_val:.3f} mm")
    report_lines.append("")
    report_lines.append("Stock Oversizes (Material Allowances):")
    report_lines.append(f"  X- (negative direction): {stock_extent_x_neg:.3f} mm")
    report_lines.append(f"  X+ (positive direction): {stock_extent_x_pos:.3f} mm")
    report_lines.append(f"  Y- (negative direction): {stock_extent_y_neg:.3f} mm")
    report_lines.append(f"  Y+ (positive direction): {stock_extent_y_pos:.3f} mm")
    report_lines.append(f"  Z- (negative direction): {stock_extent_z_neg:.3f} mm")
    report_lines.append(f"  Z+ (positive direction): {stock_extent_z_pos:.3f} mm")
    report_lines.append("")
    report_lines.append("Total Stock Dimensions (Workpiece + Oversizes):")
    report_lines.append(f"  Total Length (X): {workpiece_length_val + stock_extent_x_neg + stock_extent_x_pos:.3f} mm")
    report_lines.append(f"  Total Width (Y):  {workpiece_width_val + stock_extent_y_neg + stock_extent_y_pos:.3f} mm")
    report_lines.append(f"  Total Thickness (Z): {workpiece_thickness_val + stock_extent_z_neg + stock_extent_z_pos:.3f} mm")
    report_lines.append("")
    
    # Part dimensions and edge positions
    report_lines.append("-" * 80)
    report_lines.append("PART DIMENSIONS AND EDGE POSITIONS (Relative to Job Coordinate System)")
    report_lines.append("-" * 80)
    
    # Try to get part dimensions from Job.Model first (most accurate)
    part_length = None
    part_width = None
    part_height = None
    min_x = None
    min_y = None
    min_z = None
    max_x = None
    max_y = None
    max_z = None
    
    try:
        # First, try to get dimensions from Job.Model (bounding box)
        if hasattr(job, 'Model') and job.Model:
            model_obj = job.Model
            if hasattr(model_obj, 'Shape') and hasattr(model_obj.Shape, 'BoundBox'):
                bbox = model_obj.Shape.BoundBox
                part_length = get_float_value(bbox.XLength)
                part_width = get_float_value(bbox.YLength)
                part_height = get_float_value(bbox.ZLength)
                min_x = get_float_value(bbox.XMin)
                min_y = get_float_value(bbox.YMin)
                min_z = get_float_value(bbox.ZMin)
                max_x = get_float_value(bbox.XMax)
                max_y = get_float_value(bbox.YMax)
                max_z = get_float_value(bbox.ZMax)
                report_lines.append("(Dimensions from Job.Model bounding box)")
            elif hasattr(model_obj, 'BoundBox'):
                bbox = model_obj.BoundBox
                part_length = get_float_value(bbox.XLength)
                part_width = get_float_value(bbox.YLength)
                part_height = get_float_value(bbox.ZLength)
                min_x = get_float_value(bbox.XMin)
                min_y = get_float_value(bbox.YMin)
                min_z = get_float_value(bbox.ZMin)
                max_x = get_float_value(bbox.XMax)
                max_y = get_float_value(bbox.YMax)
                max_z = get_float_value(bbox.ZMax)
                report_lines.append("(Dimensions from Job.Model bounding box)")
        
        # If Model not available, try Base
        if part_length is None and hasattr(job, 'Base') and job.Base:
            try:
                if isinstance(job.Base, list) and len(job.Base) > 0:
                    base_obj = job.Base[0]
                elif hasattr(job.Base, 'Shape'):
                    base_obj = job.Base
                else:
                    base_obj = None
                
                if base_obj and hasattr(base_obj, 'Shape') and hasattr(base_obj.Shape, 'BoundBox'):
                    bbox = base_obj.Shape.BoundBox
                    part_length = get_float_value(bbox.XLength)
                    part_width = get_float_value(bbox.YLength)
                    part_height = get_float_value(bbox.ZLength)
                    min_x = get_float_value(bbox.XMin)
                    min_y = get_float_value(bbox.YMin)
                    min_z = get_float_value(bbox.ZMin)
                    max_x = get_float_value(bbox.XMax)
                    max_y = get_float_value(bbox.YMax)
                    max_z = get_float_value(bbox.ZMax)
                    report_lines.append("(Dimensions from Job.Base bounding box)")
            except Exception as e:
                pass
        
        # If still not available, calculate from contours (fallback)
        if part_length is None:
            try:
                min_x, min_y, min_z, max_x, max_y, max_z = calculate_part_bounds()
                min_x = get_float_value(min_x)
                min_y = get_float_value(min_y)
                min_z = get_float_value(min_z)
                max_x = get_float_value(max_x)
                max_y = get_float_value(max_y)
                max_z = get_float_value(max_z)
                part_length = max_x - min_x
                part_width = max_y - min_y
                part_height = max_z - min_z
                report_lines.append("(Dimensions calculated from contours - may be inaccurate)")
            except Exception as e:
                report_lines.append(f"<Error calculating part bounds from contours: {e}>")
        
        if part_length is not None:
            report_lines.append(f"Part Length (X): {part_length:.3f} mm")
            report_lines.append(f"Part Width (Y):  {part_width:.3f} mm")
            report_lines.append(f"Part Height (Z): {part_height:.3f} mm")
            report_lines.append("")
            report_lines.append("Part Edge Positions (Job Coordinate System):")
            report_lines.append(f"  X- (minimum X): {min_x:.3f} mm")
            report_lines.append(f"  X+ (maximum X): {max_x:.3f} mm")
            report_lines.append(f"  Y- (minimum Y): {min_y:.3f} mm")
            report_lines.append(f"  Y+ (maximum Y): {max_y:.3f} mm")
            report_lines.append(f"  Z- (minimum Z): {min_z:.3f} mm")
            report_lines.append(f"  Z+ (maximum Z): {max_z:.3f} mm")
            report_lines.append("")
            report_lines.append("Part Bounding Box:")
            report_lines.append(f"  From: ({min_x:.3f}, {min_y:.3f}, {min_z:.3f}) mm")
            report_lines.append(f"  To:   ({max_x:.3f}, {max_y:.3f}, {max_z:.3f}) mm")
        else:
            report_lines.append("<Could not determine part dimensions>")
    except Exception as e:
        report_lines.append(f"<Error calculating part dimensions: {e}>")
        import traceback
        report_lines.append(f"<Traceback: {traceback.format_exc()}>")
    
    report_lines.append("")
    
    # G54 Coordinate System Offset
    report_lines.append("-" * 80)
    report_lines.append("COORDINATE SYSTEM OFFSET (G54)")
    report_lines.append("-" * 80)
    if COORDINATE_SYSTEM:
        # Extract float values from offsets
        offset_x_val = get_float_value(COORDINATE_OFFSET_X)
        offset_y_val = get_float_value(COORDINATE_OFFSET_Y)
        offset_z_val = get_float_value(COORDINATE_OFFSET_Z)
        
        report_lines.append(f"Coordinate System: {COORDINATE_SYSTEM}")
        report_lines.append(f"Offset X: {offset_x_val:.3f} mm")
        report_lines.append(f"Offset Y: {offset_y_val:.3f} mm")
        report_lines.append(f"Offset Z: {offset_z_val:.3f} mm")
        report_lines.append("")
        report_lines.append("NOTE: This offset is applied ONLY to MPR format coordinates.")
        report_lines.append("      G-code output remains unchanged (uses original Job coordinates).")
        if min_x is not None:
            # Ensure min values are also float
            min_x_val = get_float_value(min_x)
            min_y_val = get_float_value(min_y)
            min_z_val = get_float_value(min_z)
            
            report_lines.append("")
            report_lines.append("Part minimum point (before offset):")
            report_lines.append(f"  X: {min_x_val:.3f} mm")
            report_lines.append(f"  Y: {min_y_val:.3f} mm")
            report_lines.append(f"  Z: {min_z_val:.3f} mm")
            report_lines.append("")
            report_lines.append("Part minimum point (after G54 offset, becomes 0,0,0 in MPR):")
            report_lines.append(f"  X: {min_x_val + offset_x_val:.3f} mm (should be ~0.000)")
            report_lines.append(f"  Y: {min_y_val + offset_y_val:.3f} mm (should be ~0.000)")
            report_lines.append(f"  Z: {min_z_val + offset_z_val:.3f} mm (should be ~0.000)")
    else:
        report_lines.append("Coordinate System: Project (no offset)")
        report_lines.append("Offset X: 0.000 mm")
        report_lines.append("Offset Y: 0.000 mm")
        report_lines.append("Offset Z: 0.000 mm")
        report_lines.append("")
        report_lines.append("NOTE: No coordinate system offset is applied.")
        report_lines.append("      MPR coordinates match Job coordinates.")
    
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

        # G0 (rapid move) - always treat as G1 (linear move)
        if cmd.Name in ['G0', 'G00']:
            # Check if there is actual movement (dX, dY, or dZ)
            # Skip if all movements are less than 0.001 (no actual movement)
            dx = abs(x - current_x)
            dy = abs(y - current_y)
            dz = abs(z - current_z)
            if not (dx < 0.001 and dy < 0.001 and dz < 0.001):
                line_elem = {
                    'type': 'KL',  # Line
                    'x': x,
                    'y': y,
                    'z': z,  # Always include Z coordinate
                    'move_type': 'G0'  # Store original movement type for analysis
                }
                elements.append(line_elem)

        # Linear move (G1) - create line
        elif cmd.Name in ['G1', 'G01']:
            # Check if there is actual movement (dX, dY, or dZ)
            # Skip if all movements are less than 0.001 (no actual movement)
            dx = abs(x - current_x)
            dy = abs(y - current_y)
            dz = abs(z - current_z)
            if not (dx < 0.001 and dy < 0.001 and dz < 0.001):
                line_elem = {
                    'type': 'KL',  # Line
                    'x': x,
                    'y': y,
                    'z': z,  # Always include Z coordinate
                    'move_type': 'G1'  # Store original movement type for analysis
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
                # Calculate start and end angles
                start_angle = math.atan2(current_y - center_y, current_x - center_x)
                end_angle = math.atan2(y - center_y, x - center_x)

                # Normalize angles
                if direction == 'CCW' and end_angle < start_angle:
                    end_angle += 2 * math.pi
                elif direction == 'CW' and end_angle > start_angle:
                    end_angle -= 2 * math.pi

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
                start_angle = math.atan2(current_y - center_y, current_x - center_x)
                end_angle = math.atan2(y - center_y, x - center_x)
                
                # Normalize angles for direction
                if direction == 'CCW' and end_angle < start_angle:
                    end_angle += 2 * math.pi
                elif direction == 'CW' and end_angle > start_angle:
                    end_angle -= 2 * math.pi
                
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


def calculate_part_bounds():
    """Calculate minimum and maximum X, Y, Z coordinates from all contours and operations.
    
    This finds the bounding box of the part which will be used to report
    part dimensions and edge positions relative to Job coordinate system.
    
    Returns:
        tuple: (min_x, min_y, min_z, max_x, max_y, max_z) or (0.0, 0.0, 0.0, 0.0, 0.0, 0.0) if nothing found
    """
    global contours, operations
    
    min_x = None
    min_y = None
    min_z = None
    max_x = None
    max_y = None
    max_z = None
    
    points_checked = 0
    
    # Check all contour elements
    for contour_idx, contour in enumerate(contours):
        # Check start position
        start_x, start_y, start_z = contour.get('start_pos', (0.0, 0.0, 0.0))
        if min_x is None or start_x < min_x:
            min_x = start_x
        if max_x is None or start_x > max_x:
            max_x = start_x
        if min_y is None or start_y < min_y:
            min_y = start_y
        if max_y is None or start_y > max_y:
            max_y = start_y
        if min_z is None or start_z < min_z:
            min_z = start_z
        if max_z is None or start_z > max_z:
            max_z = start_z
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
            if max_x is None or x > max_x:
                max_x = x
            if min_y is None or y < min_y:
                min_y = y
            if max_y is None or y > max_y:
                max_y = y
            if min_z is None or z < min_z:
                min_z = z
            if max_z is None or z > max_z:
                max_z = z
            points_checked += 1
            
            # For arcs, also check center point and extent
            if elem.get('type') == 'KA':  # Arc element
                center_x = prev_x + elem.get('i', 0.0)
                center_y = prev_y + elem.get('j', 0.0)
                center_z = prev_z  # Arc center Z is same as previous Z for XY plane arcs
                
                # Check center point
                if min_x is None or center_x < min_x:
                    min_x = center_x
                if max_x is None or center_x > max_x:
                    max_x = center_x
                if min_y is None or center_y < min_y:
                    min_y = center_y
                if max_y is None or center_y > max_y:
                    max_y = center_y
                if min_z is None or center_z < min_z:
                    min_z = center_z
                if max_z is None or center_z > max_z:
                    max_z = center_z
                points_checked += 1
                
                # For arcs, also check if radius extends beyond end point
                radius = elem.get('r', 0.0)
                if radius > 0.001:
                    # Check X and Y extents (center ± radius)
                    arc_min_x = center_x - radius
                    arc_max_x = center_x + radius
                    arc_min_y = center_y - radius
                    arc_max_y = center_y + radius
                    if min_x is None or arc_min_x < min_x:
                        min_x = arc_min_x
                    if max_x is None or arc_max_x > max_x:
                        max_x = arc_max_x
                    if min_y is None or arc_min_y < min_y:
                        min_y = arc_min_y
                    if max_y is None or arc_max_y > max_y:
                        max_y = arc_max_y
            
            # Update previous point for next iteration
            prev_x = x
            prev_y = y
            prev_z = z
    
    # Check all drilling operations
    for op in operations:
        if op.get('type') == 'BohrVert':
            xa = op.get('xa', 0.0)
            ya = op.get('ya', 0.0)
            depth = op.get('depth', 0.0)
            z = -depth  # Depth is negative Z
            
            if min_x is None or xa < min_x:
                min_x = xa
            if max_x is None or xa > max_x:
                max_x = xa
            if min_y is None or ya < min_y:
                min_y = ya
            if max_y is None or ya > max_y:
                max_y = ya
            if min_z is None or z < min_z:
                min_z = z
            if max_z is None or z > max_z:
                max_z = z
            points_checked += 1
    
    # Return bounds or (0,0,0,0,0,0) if nothing found
    if min_x is None:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    
    return (min_x, min_y, min_z, max_x, max_y, max_z)


def generate_mpr_content(z_safe=20.0):
    """Generate complete MPR format content and return as string.
    
    NOTE: If COORDINATE_SYSTEM is set (G54, G55, etc.), coordinates will be offset
    by the minimum part coordinates. This offset is applied ONLY to MPR format.
    G-code generation is NOT affected and remains unchanged.
    
    Args:
        z_safe: Safe height value for UF and ZS parameters (default: 20.0 mm)
    """
    global contours, operations, WORKPIECE_LENGTH, WORKPIECE_WIDTH, WORKPIECE_THICKNESS
    global STOCK_EXTENT_X, STOCK_EXTENT_Y, STOCK_EXTENT_X_NEG, STOCK_EXTENT_X_POS, STOCK_EXTENT_Y_NEG, STOCK_EXTENT_Y_POS
    global OUTPUT_COMMENTS, PRECISION, now
    global COORDINATE_SYSTEM, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y, COORDINATE_OFFSET_Z
    global PROGRAM_OFFSET_X, PROGRAM_OFFSET_Y, PROGRAM_OFFSET_Z
    global ENABLE_PROCESSING_ANALYSIS
    
    output = []

    # Initialize processing analysis file if enabled
    analysis_lines = []
    if ENABLE_PROCESSING_ANALYSIS:
        analysis_lines.append("Processing Analysis - Path Commands | Analysis | MPR Output")
        analysis_lines.append("=" * 120)

    # Header section [H
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
    # UF and ZS must reference the variable z_safe, not the value
    output.append('UF="z_safe"')
    output.append('ZS="z_safe"')
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
    # _BSX, _BSY, _BSZ are base dimensions (workpiece dimensions)
    output.append(f'_BSX={fmt(WORKPIECE_LENGTH)}')
    output.append(f'_BSY={fmt(WORKPIECE_WIDTH)}')
    output.append(f'_BSZ={fmt(WORKPIECE_THICKNESS)}')
    # _FNX, _FNY are front offsets (left and front offsets = l_off and f_off)
    output.append(f'_FNX={fmt(STOCK_EXTENT_X_NEG)}')
    output.append(f'_FNY={fmt(STOCK_EXTENT_Y_NEG)}')
    # _RNX, _RNY, _RNZ are program offsets
    output.append(f'_RNX={fmt(PROGRAM_OFFSET_X)}')
    output.append(f'_RNY={fmt(PROGRAM_OFFSET_Y)}')
    output.append(f'_RNZ={fmt(PROGRAM_OFFSET_Z)}')
    # _RX and _RY are total stock dimensions: l_off + l + r_oz and f_off + w + b_oz
    output.append(f'_RX={fmt(STOCK_EXTENT_X_NEG + WORKPIECE_LENGTH + STOCK_EXTENT_X_POS)}')
    output.append(f'_RY={fmt(STOCK_EXTENT_Y_NEG + WORKPIECE_WIDTH + STOCK_EXTENT_Y_POS)}')
    output.append('')

    # Contour elements section
    for contour in contours:
        output.append(f']{contour["id"]}')

        # Add starting point ($E0 KP)
        start_x, start_y, start_z = contour.get('start_pos', (0.0, 0.0, 0.0))
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
        # Store original (unoffset) coordinates for arc center calculations
        prev_elem_x_orig = contour.get('start_pos', (0.0, 0.0, 0.0))[0]
        prev_elem_y_orig = contour.get('start_pos', (0.0, 0.0, 0.0))[1]
        prev_elem_z_orig = contour.get('start_pos', (0.0, 0.0, 0.0))[2]
        
        # Offset coordinates for output
        prev_elem_x = start_x
        prev_elem_y = start_y
        prev_elem_z = start_z
        
        for idx, elem in enumerate(contour['elements']):
            elem_num = idx + 1
            output.append(f'$E{elem_num}')

            if elem['type'] == 'KL':  # Line
                # Original coordinates (before offset) for Path Commands
                orig_x = elem['x']
                orig_y = elem['y']
                orig_z = elem.get('z', 0.0)
                
                elem_x = elem['x'] + COORDINATE_OFFSET_X
                elem_y = elem['y'] + COORDINATE_OFFSET_Y
                z_value = elem.get('z', 0.0) + COORDINATE_OFFSET_Z
                
                output.append('KL ')
                output.append(f'X={fmt(elem_x)}')
                output.append(f'Y={fmt(elem_y)}')
                output.append(f'Z={fmt(z_value)}')
                
                # Calculate line angles
                dx = elem_x - prev_elem_x
                dy = elem_y - prev_elem_y
                dz = z_value - prev_elem_z
                
                if abs(dx) > 0.001 or abs(dy) > 0.001:
                    wi_angle = math.atan2(dy, dx)
                else:
                    wi_angle = 0.0
                
                line_length_xy = math.sqrt(dx*dx + dy*dy)
                if line_length_xy > 0.001:
                    wz_angle = math.atan2(dz, line_length_xy)
                else:
                    wz_angle = 0.0
                
                output.append(f'.X={fmt(elem_x)}')
                output.append(f'.Y={fmt(elem_y)}')
                output.append(f'.Z={fmt(z_value)}')
                output.append(f'.WI={fmt(wi_angle)}')
                output.append(f'.WZ={fmt(wz_angle)}')

                # Calculate line length
                line_length = math.sqrt(dx*dx + dy*dy + dz*dz)
                
                # Processing analysis output
                if ENABLE_PROCESSING_ANALYSIS:
                    # Determine movement type from original element (G0 or G1)
                    move_type = elem.get('move_type', 'G1')  # Default to G1
                    # Path Commands part
                    path_cmd = f"{move_type} X={orig_x} Y={orig_y} Z={orig_z}"
                    # Analysis part
                    analysis = f"l={line_length:.6f} r1= r2= angle="
                    # MPR Output part: format is contour:element type (e.g., 1:32 KL)
                    mpr_output = f"{contour['id']}:{elem_num} KL e={fmt(elem_x)},{fmt(elem_y)},{fmt(z_value)} l={fmt(line_length)} rc= rf= OK"
                    analysis_lines.append(f"{path_cmd} | {analysis} | {mpr_output}")

                prev_elem_x = elem_x
                prev_elem_y = elem_y
                prev_elem_z = z_value
                
                # Update original coordinates for next element
                prev_elem_x_orig = orig_x
                prev_elem_y_orig = orig_y
                prev_elem_z_orig = orig_z
                
            elif elem['type'] == 'KA':  # Arc
                # Original coordinates (before offset) for center calculation
                orig_x = elem['x']
                orig_y = elem['y']
                orig_z = elem.get('z', 0.0)
                
                # Offset coordinates for output
                elem_x = elem['x'] + COORDINATE_OFFSET_X
                elem_y = elem['y'] + COORDINATE_OFFSET_Y
                z_value = elem.get('z', 0.0) + COORDINATE_OFFSET_Z
                
                # CRITICAL: Calculate arc center from I, J offsets using ORIGINAL (unoffset) coordinates
                # I, J are offsets from the original previous point, not the offset one
                center_x_orig = prev_elem_x_orig + elem.get('i', 0)
                center_y_orig = prev_elem_y_orig + elem.get('j', 0)
                
                # Apply offset to center coordinates for output
                center_x = center_x_orig + COORDINATE_OFFSET_X
                center_y = center_y_orig + COORDINATE_OFFSET_Y
                
                # Calculate start and end angles using offset coordinates
                # Both points and center are already offset, so angles are correct
                start_angle = math.atan2(prev_elem_y - center_y, prev_elem_x - center_x)
                end_angle = math.atan2(elem_y - center_y, elem_x - center_x)
                
                direction = elem.get('direction', 'CW')
                
                # Normalize angles based on direction
                if direction == 'CCW' and end_angle < start_angle:
                    end_angle += 2 * math.pi
                elif direction == 'CW' and end_angle > start_angle:
                    end_angle -= 2 * math.pi
                
                # Calculate arc angle in radians
                arc_angle = abs(end_angle - start_angle)
                
                # Determine if arc is small (<=180°) or large (>180°)
                is_small_arc = arc_angle <= math.pi
                
                # STEP 1: Calculate actual radii from center to start and end points
                radius_from_start = math.sqrt((prev_elem_x - center_x)**2 + (prev_elem_y - center_y)**2)
                radius_to_end = math.sqrt((elem_x - center_x)**2 + (elem_y - center_y)**2)
                
                # Check if radii are significantly different (indicates geometry error)
                radius_diff = abs(radius_from_start - radius_to_end)
                if radius_diff > 0.001:  # More than 0.001mm difference
                    print(f"[WoodWOP WARNING] Arc geometry error: radii from center differ by {radius_diff:.3f}mm")
                    print(f"[WoodWOP WARNING]   Radius from start point: {radius_from_start:.3f}mm")
                    print(f"[WoodWOP WARNING]   Radius to end point: {radius_to_end:.3f}mm")
                    print(f"[WoodWOP WARNING]   Center: ({center_x:.3f}, {center_y:.3f})")
                    print(f"[WoodWOP WARNING]   Start: ({prev_elem_x:.3f}, {prev_elem_y:.3f})")
                    print(f"[WoodWOP WARNING]   End: ({elem_x:.3f}, {elem_y:.3f})")
                    print(f"[WoodWOP WARNING]   Using average radius: {(radius_from_start + radius_to_end) / 2.0:.3f}mm")
                
                # STEP 2: Get radius from element or calculate from geometry
                # Store initial radius BEFORE any corrections for analysis
                initial_radius = elem.get('r', 0.0)
                if initial_radius <= 0.001:
                    # No radius provided, use average of calculated radii
                    # This handles cases where radii differ slightly due to rounding
                    initial_radius = (radius_from_start + radius_to_end) / 2.0
                
                radius = initial_radius
                
                # STEP 3: Verify radius matches geometry (should be close to both calculated radii)
                # If there's a significant discrepancy (>0.001mm), recalculate from geometry
                radius_avg = (radius_from_start + radius_to_end) / 2.0
                radius_diff_start = abs(radius - radius_from_start)
                radius_diff_end = abs(radius - radius_to_end)
                
                if radius_diff_start > 0.001 or radius_diff_end > 0.001:
                    # Radius doesn't match geometry, use calculated average
                    print(f"[WoodWOP WARNING] Arc radius mismatch. Provided R={radius:.3f}, calculated from start={radius_from_start:.3f}, from end={radius_to_end:.3f}. Using calculated average: {radius_avg:.3f}")
                    radius = radius_avg
                
                # STEP 4: Calculate chord length (distance between start and end points)
                chord_length = math.sqrt((elem_x - prev_elem_x)**2 + (elem_y - prev_elem_y)**2)
                
                # STEP 5: Special check for 180° arcs - verify feasibility
                # For 180° arc, radius cannot be smaller than half the chord length
                # Example: from (0,0) to (100,0) with radius 49.999 is impossible
                # Minimum radius must be at least chord_length / 2
                if abs(arc_angle - math.pi) < 0.001:  # Arc is approximately 180°
                    # For 180° arc, ensure chord_length <= 2 * radius
                    # Keep adjusting radius until it's guaranteed to be large enough
                    iteration = 0
                    max_iterations = 10  # Safety limit to prevent infinite loop
                    while chord_length - 2 * radius > 0.0001 and iteration < max_iterations:
                        # Radius is too small for 180° arc, adjust to minimum + margin
                        radius = chord_length / 2.0 + 0.001
                        iteration += 1
                        if iteration == 1:
                            print(f"[WoodWOP WARNING] 180° arc: radius too small for chord {chord_length:.3f}. Adjusting to {radius:.3f}")
                        elif iteration > 1:
                            print(f"[WoodWOP WARNING] 180° arc: iteration {iteration}, radius adjusted to {radius:.3f}")
                    
                    if iteration >= max_iterations:
                        print(f"[WoodWOP ERROR] 180° arc: failed to correct radius after {max_iterations} iterations. Final radius: {radius:.3f}, chord: {chord_length:.3f}")
                    
                    # Final guarantee: ensure 2 * radius >= chord_length with small margin to prevent negative real_correction
                    # Add extra margin to account for rounding errors
                    min_required_radius = chord_length / 2.0 + 0.001  # Margin for rounding
                    if radius < min_required_radius:
                        radius = min_required_radius
                        print(f"[WoodWOP WARNING] 180° arc: final adjustment to prevent negative real_correction. Radius set to {radius:.6f}")
                
                # STEP 6: Final verification - ensure radius is not zero or negative
                if radius <= 0.001:
                    # Fallback: use chord length / 2 (minimum for any arc)
                    radius = max(chord_length / 2.0, 0.001)
                    print(f"[WoodWOP WARNING] Arc radius was zero or negative, set to minimum: {radius:.3f}")
                
                # STEP 7: Skip arc if radius is still too small (< 0.001)
                # Such arcs are invalid and should be skipped
                if radius < 0.001:
                    print(f"[WoodWOP WARNING] Skipping arc with radius {radius:.6f} < 0.001mm (too small, invalid geometry)")
                    print(f"[WoodWOP WARNING]   Start: ({prev_elem_x:.3f}, {prev_elem_y:.3f}), End: ({elem_x:.3f}, {elem_y:.3f})")
                    print(f"[WoodWOP WARNING]   Center: ({center_x:.3f}, {center_y:.3f}), Chord: {chord_length:.3f}mm")
                    # Update previous position but skip adding this element
                    prev_elem_x = elem_x
                    prev_elem_y = elem_y
                    prev_elem_z = z_value
                    continue  # Skip this arc element
                
                # Check if corrections were applied
                # Corrections happen in STEP 3 (geometry mismatch) or STEP 5 (180° arc)
                was_corrected = False
                if abs(radius - initial_radius) > 0.001:
                    was_corrected = True
                elif abs(arc_angle - math.pi) < 0.001:
                    # For 180° arcs, check if radius was adjusted
                    min_radius_180 = chord_length / 2.0
                    if abs(radius - min_radius_180) > 0.001 or radius > min_radius_180:
                        was_corrected = True
                
                radius_corrected = radius
                
                # Calculate real_correction for arcs: 2 * radius - chord_length
                # For 180° arcs, ensure real_correction is never negative (due to rounding errors)
                real_correction = 2 * radius - chord_length
                if abs(arc_angle - math.pi) < 0.001:  # Arc is approximately 180°
                    # Guarantee non-negative real_correction for 180° arcs
                    if real_correction < 0:
                        # Additional correction: increase radius slightly
                        radius = chord_length / 2.0 + abs(real_correction) / 2.0 + 0.001
                        real_correction = 2 * radius - chord_length
                        print(f"[WoodWOP WARNING] 180° arc: real_correction was negative ({real_correction:.8f}), adjusted radius to {radius:.6f}, new real_correction={real_correction:.8f}")
                    # Ensure real_correction is at least 0 (handle rounding to -0.00000000)
                    real_correction = max(0.0, real_correction)
                
                # Calculate arc angle in degrees for analysis
                arc_angle_deg = math.degrees(arc_angle)
                
                # Processing analysis output for arcs
                if ENABLE_PROCESSING_ANALYSIS:
                    # Original coordinates (before offset) for Path Commands
                    orig_x = elem['x']
                    orig_y = elem['y']
                    orig_z = elem.get('z', 0.0)
                    orig_i = elem.get('i', 0.0)
                    orig_j = elem.get('j', 0.0)
                    move_type = 'G2' if direction == 'CW' else 'G3'
                    
                    # Path Commands part
                    path_cmd = f"{move_type} X={orig_x} Y={orig_y} Z={orig_z} I={orig_i} J={orig_j}"
                    # Analysis part
                    analysis = f"ch={chord_length:.6f} r1={radius_from_start:.6f} r2={radius_to_end:.6f} angle={arc_angle_deg:.6f}"
                    # MPR Output part: format is contour:element type (e.g., 1:32 KA)
                    correction_status = "CORR" if was_corrected else "OK"
                    # real_correction only for 180° arcs
                    if abs(arc_angle - math.pi) < 0.001:
                        mpr_output = f"{contour['id']}:{elem_num} KA e={fmt(elem_x)},{fmt(elem_y)},{fmt(z_value)} l={fmt(chord_length)} rc={fmt(initial_radius)} rf={fmt(radius_corrected)} {correction_status} rcorr={real_correction:.8f}"
                    else:
                        mpr_output = f"{contour['id']}:{elem_num} KA e={fmt(elem_x)},{fmt(elem_y)},{fmt(z_value)} l={fmt(chord_length)} rc={fmt(initial_radius)} rf={fmt(radius_corrected)} {correction_status}"
                    analysis_lines.append(f"{path_cmd} | {analysis} | {mpr_output}")
                
                # Calculate DS value based on direction and arc size
                # DS=0: CW small arc (<=180°)
                # DS=1: CCW small arc (<=180°)
                # DS=2: CW large arc (>180°)
                # DS=3: CCW large arc (>180°)
                if direction == 'CW':
                    ds_value = 0 if is_small_arc else 2
                else:  # CCW
                    ds_value = 1 if is_small_arc else 3
                
                # Main block: only X, Y, Z, DS, R (no I, J)
                output.append('KA ')
                output.append(f'X={fmt(elem_x)}')
                output.append(f'Y={fmt(elem_y)}')
                output.append(f'Z={fmt(z_value)}')
                output.append(f'DS={ds_value}')
                output.append(f'R={fmt(radius)}')
                
                # Calculated block: all parameters for compatibility
                waz_angle = 0.0
                output.append(f'.X={fmt(elem_x)}')
                output.append(f'.Y={fmt(elem_y)}')
                output.append(f'.Z={fmt(z_value)}')
                output.append(f'.I={fmt(center_x)}')
                output.append(f'.J={fmt(center_y)}')
                output.append(f'.DS={ds_value}')
                output.append(f'.R={fmt(radius)}')
                output.append(f'.WI={fmt(start_angle)}')
                output.append(f'.WO={fmt(end_angle)}')
                output.append(f'.WAZ={fmt(waz_angle)}')
                
                prev_elem_x = elem_x
                prev_elem_y = elem_y
                prev_elem_z = z_value
                
                # Update original coordinates for next element
                prev_elem_x_orig = orig_x
                prev_elem_y_orig = orig_y
                prev_elem_z_orig = orig_z

            output.append('')

        output.append('')

    # Variables and workpiece section
    # According to WoodWOP MPR standard, variables in [001] section must be written WITH quotes around values
    output.append('[001')
    output.append(f'l="{fmt(WORKPIECE_LENGTH)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="length in X"')
    output.append(f'w="{fmt(WORKPIECE_WIDTH)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="width in Y"')
    output.append(f'th="{fmt(WORKPIECE_THICKNESS)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="thickness in Z"')
    output.append(f'x="{fmt(PROGRAM_OFFSET_X)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="offset programs in x"')
    output.append(f'y="{fmt(PROGRAM_OFFSET_Y)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="offset programs in y"')
    output.append(f'z="{fmt(PROGRAM_OFFSET_Z)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="z offset"')
    output.append(f'l_off="{fmt(STOCK_EXTENT_X_NEG)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="left offset"')
    output.append(f'f_off="{fmt(STOCK_EXTENT_Y_NEG)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="front offset"')
    output.append(f'r_oz="{fmt(STOCK_EXTENT_X_POS)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="right oversize"')
    output.append(f'b_oz="{fmt(STOCK_EXTENT_Y_POS)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="back oversize"')
    output.append(f'z_safe="{fmt(z_safe)}"')
    if OUTPUT_COMMENTS:
        output.append('KM="clearance height"')
    output.append('')

    output.append(f'<100 \\WerkStck\\')
    output.append(f'LA="l"')
    output.append(f'BR="w"')
    output.append(f'DI="th"')
    # FNX and FNY must reference variables, not values
    output.append(f'FNX="l_off"')
    output.append(f'FNY="f_off"')
    # RNX, RNY, RNZ must reference variables x, y, z
    output.append(f'RNX="x"')
    output.append(f'RNY="y"')
    output.append(f'RNZ="z"')
    # RL and RB are formulas
    output.append(f'RL="l_off+l+r_oz"')
    output.append(f'RB="f_off+w+b_oz"')
    output.append('')

    if OUTPUT_COMMENTS:
        output.append('<101 \\Kommentar\\')
        output.append(f'KM="Generated by FreeCAD WoodWOP Post Processor"')
        output.append(f'KM="Date: {now.strftime("%Y-%m-%d %H:%M:%S")}"')
        if COORDINATE_SYSTEM:
            output.append(f'KM="Coordinate System: {COORDINATE_SYSTEM} (offset: X={COORDINATE_OFFSET_X:.3f}, Y={COORDINATE_OFFSET_Y:.3f}, Z={COORDINATE_OFFSET_Z:.3f})"')
        output.append('KAT="Kommentar"')
        output.append('MNM="Kommentar"')
        output.append('ORI="1"')
        output.append('')

    # Operations section
    for op in operations:
        if op['type'] == 'BohrVert':
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

    # End of file
    output.append('!')

    # CRITICAL DEBUG: Check output before joining
    print(f"[WoodWOP DEBUG] generate_mpr_content() output list length: {len(output)}")
    if len(output) == 0:
        error_msg = "[WoodWOP CRITICAL ERROR] output list is EMPTY! Nothing was added to output!"
        print(error_msg)
        try:
            Path.Log.error(error_msg)
        except:
            pass
        # Return minimal valid MPR file
        minimal_mpr = '[H\r\nVERSION="4.0 Alpha"\r\n]H\r\n[001\r\nz_safe=20.0\r\n]001\r\n!'
        print(f"[WoodWOP DEBUG] Returning minimal MPR file (length: {len(minimal_mpr)})")
        return minimal_mpr
    
    # Save processing analysis file if enabled
    if ENABLE_PROCESSING_ANALYSIS and len(analysis_lines) > 0:
        try:
            import os
            import FreeCAD
            # Get base filename from Job or use default
            base_filename = "processing_analysis"
            try:
                doc = FreeCAD.ActiveDocument
                if doc:
                    for obj in doc.Objects:
                        if hasattr(obj, 'Proxy') and 'Job' in str(type(obj.Proxy)):
                            if hasattr(obj, 'PostProcessorOutputFile') and obj.PostProcessorOutputFile:
                                base_filename = os.path.splitext(os.path.basename(obj.PostProcessorOutputFile))[0]
                                break
                            elif hasattr(obj, 'Model') and obj.Model:
                                if hasattr(obj.Model, 'Label'):
                                    base_filename = obj.Model.Label.replace(' ', '_')
                                    break
            except:
                pass
            
            # Determine output directory
            output_dir = os.getcwd()
            try:
                doc = FreeCAD.ActiveDocument
                if doc and hasattr(doc, 'FileName') and doc.FileName:
                    output_dir = os.path.dirname(doc.FileName)
            except:
                pass
            
            analysis_filename = os.path.join(output_dir, f"{base_filename}_processing_analysis.txt")
            with open(analysis_filename, 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n'.join(analysis_lines))
            print(f"[WoodWOP] Processing analysis exported to: {analysis_filename}")
        except Exception as e:
            print(f"[WoodWOP ERROR] Failed to write processing analysis file: {e}")
    
    # Return the complete MPR content as a string with CRLF line endings
    # MPR format requires CRLF (\r\n) for Windows compatibility
    result = '\r\n'.join(output)
    
    print(f"[WoodWOP DEBUG] generate_mpr_content() result length: {len(result)} characters")
    print(f"[WoodWOP DEBUG] First 500 chars of result: {result[:500]}")
    
    # Validate result is not empty
    if len(result) == 0:
        error_msg = "[WoodWOP CRITICAL ERROR] generate_mpr_content() result is EMPTY after join!"
        print(error_msg)
        try:
            Path.Log.error(error_msg)
        except:
            pass
        # Return minimal valid MPR file
        minimal_mpr = '[H\r\nVERSION="4.0 Alpha"\r\n]H\r\n[001\r\nz_safe=20.0\r\n]001\r\n!'
        print(f"[WoodWOP DEBUG] Returning minimal MPR file (length: {len(minimal_mpr)})")
        return minimal_mpr
    
    return result


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


def export_path_commands(objectslist, output_filename):
    """Export all Path Commands from all operations to a text file.
    
    Args:
        objectslist: List of FreeCAD Path objects to process
        output_filename: Full path to the output file
    
    Returns:
        bool: True if file was created successfully, False otherwise
    """
    try:
        import datetime
        from PathScripts import PathUtils
        
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append("FreeCAD Path Commands Export")
        output_lines.append("=" * 80)
        output_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"Post Processor: WoodWOP MPR")
        output_lines.append("")
        
        operation_count = 0
        total_commands = 0
        
        # Process all path objects
        for obj in objectslist:
            if not hasattr(obj, "Path"):
                continue
            
            # Get operation info
            op_label = obj.Label if hasattr(obj, 'Label') else 'Unknown'
            op_type = get_operation_type(obj)
            tool_number = get_tool_number(obj)
            
            output_lines.append("-" * 80)
            output_lines.append(f"Operation: {op_label}")
            output_lines.append(f"Type: {op_type}")
            output_lines.append(f"Tool: {tool_number}")
            output_lines.append("-" * 80)
            output_lines.append("")
            
            # Get path commands
            try:
                path_commands = PathUtils.getPathWithPlacement(obj).Commands
            except:
                path_commands = obj.Path.Commands if hasattr(obj.Path, 'Commands') else []
            
            if not path_commands:
                output_lines.append("(No commands found)")
                output_lines.append("")
                continue
            
            # Export all commands
            command_num = 0
            for cmd in path_commands:
                command_num += 1
                total_commands += 1
                
                # Format command line
                line = f"{command_num:4d}. {cmd.Name}"
                
                # Add parameters
                if cmd.Parameters:
                    for param, value in sorted(cmd.Parameters.items()):
                        line += f" {param}{fmt(value)}"
                
                output_lines.append(line)
            
            output_lines.append("")
            output_lines.append(f"Total commands in this operation: {command_num}")
            output_lines.append("")
            operation_count += 1
        
        # Summary
        output_lines.append("=" * 80)
        output_lines.append("Summary")
        output_lines.append("=" * 80)
        output_lines.append(f"Total operations: {operation_count}")
        output_lines.append(f"Total commands: {total_commands}")
        output_lines.append("")
        output_lines.append("=" * 80)
        output_lines.append("End of Export")
        output_lines.append("=" * 80)
        
        # Write to file
        with open(output_filename, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(output_lines))
        
        print(f"[WoodWOP] Path commands exported to: {output_filename}")
        print(f"[WoodWOP]   Operations: {operation_count}, Commands: {total_commands}")
        return True
        
    except Exception as e:
        print(f"[WoodWOP ERROR] Failed to export path commands: {e}")
        import traceback
        print(f"[WoodWOP ERROR] Traceback:\n{traceback.format_exc()}")
        return False


def linenumber():
    """Not used in MPR format."""
    return ''
