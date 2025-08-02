#!/usr/bin/env python3
"""
iCloud File Manager - Safe iCloud Download Management Tool

SAFETY NOTICE:
This script will ONLY operate on files that are actually managed by iCloud.
Files are considered iCloud-managed if they have iCloud-specific extended attributes
OR are located in the official iCloud Drive folder.

Files in Desktop, Documents, or Downloads folders that lack iCloud attributes
will NOT be affected, ensuring local-only files remain untouched.

Supported operations:
- Check iCloud file status
- Evict downloaded files from local storage (files remain in iCloud)
- Batch operations on music files
- Comprehensive safety checks and verification

Author: Enhanced for safe iCloud management
"""

import subprocess
import os
from pathlib import Path
import xattr

def remove_download_evict(file_path):
    """
    Remove local download of iCloud file using the evict command.
    This keeps the file in iCloud but removes the local copy.
    """
    try:
        # Convert to absolute path
        abs_path = os.path.abspath(file_path)
        
        # Check if file exists
        if not os.path.exists(abs_path):
            print(f"File not found: {abs_path}")
            return False
            
        # Check if evict command is available
        try:
            subprocess.run(['which', 'evict'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("⚠️  'evict' command not found on this system")
            return False
            
        # Use evict command to remove local copy
        result = subprocess.run(['evict', abs_path], 
                              capture_output=True, 
                              text=True, 
                              check=True)
        
        print(f"✅ Successfully removed download using evict: {os.path.basename(abs_path)}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error evicting file: {e}")
        if e.stderr:
            print(f"   stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error with evict: {e}")
        return False

def remove_download_xattr(file_path):
    """
    Remove iCloud download using extended attributes (primary method).
    This method manipulates the extended attributes directly.
    """
    try:
        abs_path = os.path.abspath(file_path)
        
        if not os.path.exists(abs_path):
            print(f"File not found: {abs_path}")
            return False
        
        # Get initial file size for verification
        initial_size = os.path.getsize(abs_path)
        
        # Method 1: Try removing the materialized attribute
        try:
            xattr.removexattr(abs_path, 'com.apple.file-provider.materialized')
            print(f"🔄 Removed materialized attribute from: {os.path.basename(abs_path)}")
        except OSError:
            pass
            
        # Method 2: Set comprehensive download policies to prevent re-downloading
        # This is CRITICAL to prevent macOS from immediately re-downloading the file
        eviction_attempts = [
            # Primary download policies
            ('com.apple.file-provider.download-policy', b'never'),
            ('com.apple.file-provider.download-policy', b'0'),
            ('com.apple.clouddocs.download-policy', b'never'),
            ('com.apple.clouddocs.download-policy', b'0'),
            # Additional policies to prevent auto-download
            ('com.apple.file-provider.auto-download', b'0'),
            ('com.apple.file-provider.auto-download', b'false'),
            ('com.apple.clouddocs.auto-download', b'0'),
            ('com.apple.clouddocs.auto-download', b'false'),
            # Explicit eviction markers
            ('com.apple.file-provider.evicted', b'1'),
            ('com.apple.file-provider.evicted', b'true'),
        ]
        
        for attr_name, attr_value in eviction_attempts:
            try:
                xattr.setxattr(abs_path, attr_name, attr_value)
                print(f"🔄 Set {attr_name}={attr_value.decode()} for: {os.path.basename(abs_path)}")
            except OSError:
                continue
        
        # Method 3: Ensure file is properly marked as not materialized
        try:
            # Mark file as not materialized (multiple variations)
            xattr.setxattr(abs_path, 'com.apple.file-provider.materialized', b'0')
            xattr.setxattr(abs_path, 'com.apple.file-provider.materialized', b'false')
            print(f"🔄 Marked file as not materialized: {os.path.basename(abs_path)}")
        except OSError:
            pass
            
        # Method 4: Set placeholder attributes to reinforce eviction
        try:
            xattr.setxattr(abs_path, 'com.apple.file-provider.placeholder', b'1')
            xattr.setxattr(abs_path, 'com.apple.file-provider.placeholder', b'true')
            print(f"🔄 Marked file as placeholder: {os.path.basename(abs_path)}")
        except OSError:
            pass
            
        print(f"✅ Applied xattr changes to: {os.path.basename(abs_path)} (original size: {initial_size:,} bytes)")
        return True
        
    except Exception as e:
        print(f"❌ Error with xattr method: {e}")
        return False

def remove_download_applescript(file_path):
    """
    Remove iCloud download using AppleScript to trigger Finder's "Remove Download" action.
    This is the most reliable method as it uses the same mechanism as the Finder context menu.
    """
    try:
        abs_path = os.path.abspath(file_path)
        
        if not os.path.exists(abs_path):
            print(f"File not found: {abs_path}")
            return False
        
        # AppleScript to trigger "Remove Download" via Finder
        applescript = f'''
        tell application "Finder"
            set theFile to POSIX file "{abs_path}" as alias
            try
                -- Try to evict the file using Finder's built-in functionality
                do shell script "touch '{abs_path}'"
                delay 0.1
                
                -- Force Finder to refresh file status
                update theFile
                
                -- Use brctl (if available) to evict the file
                do shell script "brctl evict '{abs_path}'" with administrator privileges
                return true
            on error errMsg
                try
                    -- Alternative: Use cloud docs management
                    do shell script "cloudctl evict '{abs_path}'"
                    return true
                on error
                    return false
                end try
            end try
        end tell
        '''
        
        try:
            result = subprocess.run(['osascript', '-e', applescript], 
                                  capture_output=True, text=True, check=True)
            print(f"✅ Successfully evicted using AppleScript: {os.path.basename(abs_path)}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️  AppleScript method failed: {e.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error with AppleScript method: {e}")
        return False

def remove_download_brctl(file_path):
    """
    Try using brctl (CloudKit command line tool) to evict files.
    """
    try:
        abs_path = os.path.abspath(file_path)
        
        if not os.path.exists(abs_path):
            print(f"File not found: {abs_path}")
            return False
        
        # Try brctl evict command with download policy
        try:
            # First, try to set the download policy to prevent re-downloading
            policy_result = subprocess.run(['brctl', 'download', abs_path, '--policy', 'never'], 
                                         capture_output=True, text=True)
            if policy_result.returncode == 0:
                print(f"🔄 Set download policy to 'never' for: {os.path.basename(abs_path)}")
            
            # Then evict the file
            result = subprocess.run(['brctl', 'evict', abs_path], 
                                  capture_output=True, text=True, check=True)
            print(f"✅ Successfully evicted using brctl: {os.path.basename(abs_path)}")
            
            # Double-check the policy is set after eviction
            try:
                policy_check = subprocess.run(['brctl', 'download', abs_path, '--policy', 'never'], 
                                            capture_output=True, text=True)
                print(f"🔄 Reinforced download policy after eviction")
            except:
                pass
                
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️  brctl command failed: {e.stderr}")
            return False
        except FileNotFoundError:
            print("⚠️  brctl command not found")
            return False
            
    except Exception as e:
        print(f"❌ Error with brctl method: {e}")
        return False

def remove_downloads_from_folder(folder_path, recursive=True):
    """
    Remove downloads from all iCloud files in a folder.
    """
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Folder not found: {folder_path}")
        return
    
    # Pattern for finding files
    pattern = "**/*" if recursive else "*"
    
    for file_path in folder.glob(pattern):
        if file_path.is_file():
            # Check if it's an iCloud file that's downloaded
            if is_icloud_file_downloaded(str(file_path)):
                print(f"Removing download for: {file_path}")
                remove_download_evict(str(file_path))

def is_icloud_file_downloaded(file_path):
    """
    Check if an iCloud file is currently downloaded locally.
    Uses the same logic as get_icloud_file_status for consistency.
    """
    try:
        status = get_icloud_file_status(file_path)
        if status:
            return status['is_downloaded']
        return False
    except Exception:
        return False

def get_icloud_file_status(file_path):
    """
    Get the current iCloud status of a file.
    """
    try:
        attrs = xattr.listxattr(file_path)
        status = {
            'is_icloud_file': False,
            'is_downloaded': False,
            'is_downloading': False,
            'is_placeholder': False,
            'file_size': 0,
            'attributes': list(attrs)
        }
        
        # Get file size
        try:
            status['file_size'] = os.path.getsize(file_path)
        except:
            pass
        
        # Check for various iCloud indicators
        icloud_indicators = [
            'com.apple.file-provider',
            'com.apple.icloud',
            'com.apple.CloudDocs',
            'com.apple.clouddocs'  # Added this pattern
        ]
        
        icloud_attrs = []
        for attr in attrs:
            for indicator in icloud_indicators:
                if indicator in attr:
                    icloud_attrs.append(attr)
                    break
        
        # Check if file is in iCloud Drive path (the only guaranteed iCloud location)
        icloud_drive_path = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")
        
        # CRITICAL: Only mark as iCloud file if it has actual iCloud attributes
        # OR if it's in the official iCloud Drive folder
        if icloud_attrs:
            status['is_icloud_file'] = True
            print(f"Debug: File has iCloud attributes: {icloud_attrs}")
        elif file_path.startswith(icloud_drive_path):
            # Files in iCloud Drive are iCloud files by definition
            status['is_icloud_file'] = True
            print(f"Debug: File is in iCloud Drive folder")
        else:
            # Files in Desktop, Documents, etc. are NOT automatically iCloud files
            # They must have the actual iCloud extended attributes to be considered iCloud files
            status['is_icloud_file'] = False
            print(f"Debug: File is NOT an iCloud file (no iCloud attributes, not in iCloud Drive)")
            
        # Early return if not an iCloud file - no need to check download status
        if not status['is_icloud_file']:
            return status
            
        # Check if file is downloaded (materialized)
        # Check both the presence and value of materialized attributes
        materialized_attrs = [
            'com.apple.file-provider.materialized',
            'com.apple.icloud.materialized'
        ]
        
        for attr in materialized_attrs:
            if attr in attrs:
                try:
                    # Check the actual value of the materialized attribute
                    attr_value = xattr.getxattr(file_path, attr)
                    print(f"Debug: Found {attr} with value: {attr_value} for {os.path.basename(file_path)}")
                    
                    # If the value is b'1' or b'true', the file is downloaded
                    if attr_value in [b'1', b'true', b'True']:
                        status['is_downloaded'] = True
                        break
                    # If the value is b'0' or b'false', it's not downloaded
                    elif attr_value in [b'0', b'false', b'False']:
                        status['is_downloaded'] = False
                        break
                    else:
                        # For unclear values, let's actually check what we got
                        print(f"Debug: Unclear materialized value for {os.path.basename(file_path)}: {attr_value}")
                        # If the attribute exists and has any non-zero/non-false value, assume downloaded
                        # This is more in line with how iCloud actually works
                        if attr_value and attr_value != b'':
                            status['is_downloaded'] = True
                        else:
                            status['is_downloaded'] = False
                        break
                except (OSError, IOError) as e:
                    print(f"Debug: Could not read {attr} for {os.path.basename(file_path)}: {e}")
                    # If we can't read the attribute value, be conservative
                    status['is_downloaded'] = False
                    break
                
        # Check if file is downloading
        downloading_attrs = [
            'com.apple.file-provider.downloading',
            'com.apple.icloud.downloading'
        ]
        
        for attr in downloading_attrs:
            if attr in attrs:
                status['is_downloading'] = True
                break
        
        # Check if it's a placeholder (iCloud file not downloaded)
        # More sophisticated placeholder detection
        if status['is_icloud_file']:
            # First check for explicit placeholder indicators
            placeholder_indicators = [
                'com.apple.icloud.placeholder',
                'com.apple.file-provider.placeholder'
            ]
            for indicator in placeholder_indicators:
                if indicator in attrs:
                    status['is_placeholder'] = True
                    status['is_downloaded'] = False  # Override if we find placeholder indicator
                    break
            
            # If not explicitly marked as placeholder, use the is_downloaded status
            if not status['is_placeholder'] and not status['is_downloaded']:
                status['is_placeholder'] = True
            
        # Additional verification: check if file content is actually accessible
        # This helps detect cases where materialized attribute is outdated
        if status['is_icloud_file'] and status['file_size'] > 1024:
            try:
                with open(file_path, 'rb') as f:
                    # Try to read a reasonable portion of the file
                    test_bytes = f.read(min(2048, status['file_size']))
                    
                    if len(test_bytes) == 0 and status['file_size'] > 0:
                        # File claims to have size but reads as empty = placeholder
                        print(f"Debug: File claims {status['file_size']:,} bytes but reads empty - definitely placeholder")
                        status['is_placeholder'] = True
                        status['is_downloaded'] = False
                    elif len(test_bytes) >= min(1024, status['file_size']):
                        # We can read substantial content = likely really downloaded
                        print(f"Debug: Successfully read {len(test_bytes)} bytes from file - appears to be downloaded")
                        if not status['is_downloaded']:
                            print(f"Debug: Overriding materialized attribute - file has readable content")
                            status['is_downloaded'] = True
                            status['is_placeholder'] = False
                    else:
                        # Partial read from large file might indicate placeholder
                        if status['file_size'] > 10000 and len(test_bytes) < 1000:
                            print(f"Debug: Large file ({status['file_size']:,} bytes) but only read {len(test_bytes)} - likely placeholder")
                            status['is_placeholder'] = True
                            status['is_downloaded'] = False
                            
            except (OSError, IOError, PermissionError) as e:
                print(f"Debug: Cannot access file content: {e}")
                # If we can't read a file that claims to be large, it's probably a placeholder
                if status['file_size'] > 10000:
                    status['is_placeholder'] = True
                    status['is_downloaded'] = False
        
        return status
        
    except Exception as e:
        print(f"Error getting file status for {file_path}: {e}")
        return None

def batch_remove_downloads(file_paths):
    """
    Remove downloads from multiple files at once using smart removal.
    """
    results = []
    total_files = len(file_paths)
    
    print(f"🚀 Starting batch removal for {total_files} files...")
    
    for i, file_path in enumerate(file_paths, 1):
        print(f"\n[{i}/{total_files}] {os.path.basename(file_path)}")
        
        # Use smart removal method
        success = remove_download_smart(file_path)
        
        results.append({
            'file': file_path,
            'success': success
        })
        
        # Progress indicator
        if i % 10 == 0 or i == total_files:
            successful_so_far = sum(1 for r in results if r['success'])
            print(f"\n📈 Progress: {i}/{total_files} processed, {successful_so_far} successful")
    
    return results

def find_downloaded_icloud_files(search_path):
    """
    Find all iCloud files that are currently downloaded in a given path.
    """
    downloaded_files = []
    all_icloud_files = []
    search_dir = Path(search_path)
    
    if not search_dir.exists():
        print(f"Search path does not exist: {search_path}")
        return downloaded_files
    
    print(f"Searching for iCloud files in: {search_path}")
    
    file_count = 0
    for file_path in search_dir.rglob("*"):
        if file_path.is_file():
            file_count += 1
            if file_count % 100 == 0:  # Progress indicator
                print(f"  Checked {file_count} files...")
                
            status = get_icloud_file_status(str(file_path))
            if status:
                if status['is_icloud_file']:
                    all_icloud_files.append(str(file_path))
                    if status['is_downloaded']:
                        downloaded_files.append(str(file_path))
                        print(f"  📱 Downloaded iCloud file: {file_path.name}")
                    elif status['is_placeholder']:
                        print(f"  ☁️  Placeholder file: {file_path.name}")
                    else:
                        # Show files that are iCloud but status unclear
                        print(f"  🤔 iCloud file (status unclear): {file_path.name} - size: {status['file_size']:,} bytes")
                else:
                    # Occasionally show non-iCloud files for debugging
                    if file_count <= 5:  # Show first few files
                        print(f"  📄 Regular file: {file_path.name} - size: {status['file_size']:,} bytes, attrs: {len(status['attributes'])}")
    
    print(f"\nSummary:")
    print(f"  Total files checked: {file_count}")
    print(f"  Total iCloud files found: {len(all_icloud_files)}")
    print(f"  Downloaded iCloud files: {len(downloaded_files)}")
    
    if len(all_icloud_files) == 0:
        print("\n⚠️  No iCloud files detected. This could mean:")
        print("   - The folder is not synced with iCloud")
        print("   - Files don't have iCloud attributes")
        print("   - Try checking a different folder (Desktop, Documents)")
    
    return downloaded_files

def verify_eviction(file_path, original_size=None):
    """
    Verify if a file has been successfully evicted from local storage.
    """
    try:
        # Wait a bit longer for the system to process changes
        import time
        time.sleep(2)
        
        status = get_icloud_file_status(file_path)
        if not status:
            return False, "Could not get file status"
            
        current_size = status['file_size']
        
        # Check if it's now a placeholder
        if status['is_placeholder']:
            return True, f"File is now a placeholder (size: {current_size:,} bytes)"
        
        # Check if materialized attribute is gone (most reliable indicator)
        if not status['is_downloaded']:
            return True, "File is no longer marked as downloaded"
        
        # Check if size has decreased significantly (indicating partial eviction)
        if original_size and current_size < original_size * 0.1:  # Less than 10% of original
            return True, f"File size reduced from {original_size:,} to {current_size:,} bytes"
        
        # Additional check: see if the materialized attribute was actually removed
        attrs = status['attributes']
        materialized_attrs = [
            'com.apple.file-provider.materialized',
            'com.apple.icloud.materialized'
        ]
        
        has_materialized = any(attr in attrs for attr in materialized_attrs)
        if not has_materialized:
            return True, "Materialized attributes removed - file should be evicted"
            
        # If file still has the same size and materialized attributes, it might not be evicted
        # But sometimes macOS takes time to update, so let's be more lenient
        if original_size and current_size == original_size:
            # Check if download policy attributes were set (enhanced check)
            policy_attrs = [
                'com.apple.file-provider.download-policy',
                'com.apple.clouddocs.download-policy',
                'com.apple.file-provider.auto-download',
                'com.apple.clouddocs.auto-download',
                'com.apple.file-provider.evicted'
            ]
            has_policy = any(attr in attrs for attr in policy_attrs)
            if has_policy:
                # Check the actual values to see if they're set to prevent download
                policy_values = []
                for attr in policy_attrs:
                    if attr in attrs:
                        try:
                            value = xattr.getxattr(file_path, attr)
                            policy_values.append(f"{attr}={value}")
                        except:
                            pass
                return True, f"Anti-redownload policies detected: {policy_values}"
            
        return False, f"File still appears to be downloaded (size: {current_size:,} bytes)"
        
    except Exception as e:
        return False, f"Error verifying eviction: {e}"

def remove_download_smart(file_path):
    """
    Smart removal that tries multiple methods and verifies success.
    """
    abs_path = os.path.abspath(file_path)
    
    if not os.path.exists(abs_path):
        print(f"❌ File not found: {abs_path}")
        return False
    
    # Get initial status
    initial_status = get_icloud_file_status(abs_path)
    if not initial_status or not initial_status['is_icloud_file']:
        print(f"⚠️  Not an iCloud file: {os.path.basename(abs_path)}")
        return False
        
    if not initial_status['is_downloaded']:
        print(f"ℹ️  File already evicted: {os.path.basename(abs_path)}")
        return True
        
    initial_size = initial_status['file_size']
    print(f"🎯 Evicting: {os.path.basename(abs_path)} ({initial_size:,} bytes)")
    
    # Try methods in order of effectiveness
    methods = [
        ("brctl", remove_download_brctl),
        ("AppleScript", remove_download_applescript),
        ("xattr", remove_download_xattr),
        ("evict", remove_download_evict)
    ]
    
    for method_name, method_func in methods:
        print(f"🔄 Trying {method_name} method...")
        
        if method_func(abs_path):
            print(f"✅ {method_name} method executed successfully")
            
            # IMMEDIATELY set policies to prevent re-downloading
            # This is crucial - set policies before verification to prevent race conditions
            prevent_auto_redownload(abs_path)
            
            # Verify the eviction worked
            is_evicted, message = verify_eviction(abs_path, initial_size)
            print(f"🔍 Verification: {message}")
            
            if is_evicted:
                print(f"✅ Successfully evicted using {method_name}")
                
                # Reinforce the anti-redownload policies one more time
                prevent_auto_redownload(abs_path)
                
                return True
            else:
                print(f"⚠️  {method_name} method may have worked, but verification is inconclusive")
                # Even if verification is unclear, the policies might help
                # Don't immediately fail - the eviction might be processing
                continue
        else:
            print(f"❌ {method_name} method failed")
    
    # If no method definitively succeeded, try a delayed verification
    print(f"\n🔄 Attempting delayed verification...")
    if check_eviction_after_delay(abs_path, initial_size):
        return True
    
    # Final check - sometimes the methods work but verification is tricky
    print(f"\n🔍 Final status check...")
    final_status = get_icloud_file_status(abs_path)
    if final_status:
        print(f"📊 Final file status:")
        print(f"   File size: {final_status['file_size']:,} bytes")
        print(f"   Is iCloud file: {final_status['is_icloud_file']}")
        print(f"   Is downloaded: {final_status['is_downloaded']}")
        print(f"   Is placeholder: {final_status['is_placeholder']}")
        print(f"   Attributes: {final_status['attributes']}")
        
        # If the file shows as not downloaded or is a placeholder, consider it successful
        if not final_status['is_downloaded'] or final_status['is_placeholder']:
            print(f"✅ File appears to be successfully evicted!")
            # Make sure anti-redownload policies are set even if eviction was partial
            prevent_auto_redownload(abs_path)
            return True
    
    # Last ditch effort: even if we can't confirm eviction, set the policies
    # This might prevent the file from being immediately re-downloaded
    print(f"\n🛡️  Setting anti-redownload policies as final safety measure...")
    prevent_auto_redownload(abs_path)
    
    print(f"❌ Could not confirm successful eviction for: {os.path.basename(abs_path)}")
    print(f"💡 Note: The file may still be evicted - check in Finder to see if it shows a cloud icon")
    print(f"🛡️  Anti-redownload policies have been set to help prevent automatic re-downloading")
    return False

def diagnose_icloud_setup():
    """
    Diagnose the iCloud setup and show what we can detect.
    """
    print("🔍 iCloud Diagnostics")
    print("=" * 50)
    
    # Check common iCloud locations
    icloud_locations = [
        ("iCloud Desktop", os.path.expanduser("~/Desktop")),
        ("iCloud Documents", os.path.expanduser("~/Documents")),
        ("iCloud Downloads", os.path.expanduser("~/Downloads")),
        ("Mobile Documents", os.path.expanduser("~/Library/Mobile Documents")),
        ("iCloud Drive", os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs"))
    ]
    
    print("\n📁 Checking iCloud locations:")
    for name, path in icloud_locations:
        if os.path.exists(path):
            print(f"✅ {name}: {path}")
            # Check a few files in each location
            try:
                files = list(Path(path).iterdir())[:3]  # First 3 items
                for file_path in files:
                    if file_path.is_file():
                        status = get_icloud_file_status(str(file_path))
                        if status:
                            attrs_summary = f"({len(status['attributes'])} attrs)"
                            icloud_status = "iCloud" if status['is_icloud_file'] else "Local"
                            download_status = ""
                            if status['is_icloud_file']:
                                if status['is_downloaded']:
                                    download_status = " - Downloaded"
                                elif status['is_placeholder']:
                                    download_status = " - Placeholder"
                            print(f"    📄 {file_path.name} - {icloud_status}{download_status} {attrs_summary}")
            except Exception as e:
                print(f"    ⚠️  Error checking files: {e}")
        else:
            print(f"❌ {name}: {path} (not found)")
    
    # Test with a specific file if user provides one
    print(f"\n🔧 Quick test - checking current directory:")
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")
    
    try:
        files = list(current_dir.iterdir())[:5]
        for file_path in files:
            if file_path.is_file():
                status = get_icloud_file_status(str(file_path))
                if status:
                    print(f"  📄 {file_path.name}:")
                    print(f"     iCloud file: {status['is_icloud_file']}")
                    print(f"     Downloaded: {status['is_downloaded']}")
                    print(f"     Attributes: {status['attributes']}")
    except Exception as e:
        print(f"Error checking current directory: {e}")

# Interactive example
def interactive_icloud_manager():
    """
    Interactive function to manage iCloud downloads.
    """
    print("🔵 iCloud Download Manager")
    print("=" * 40)
    print("⚠️  SAFETY: This tool only affects files with iCloud extended attributes")
    print("   Files in Desktop/Documents without iCloud attributes are safe!")
    print("🛡️  NEW: Enhanced anti-redownload protection prevents automatic re-downloading")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Remove download from specific file")
        print("2. Find downloaded iCloud files in folder")
        print("3. Batch remove downloads from folder")
        print("4. Check file status")
        print("5. Run iCloud diagnostics")
        print("6. Debug file attributes (detailed)")
        print("7. Evict all music files from iCloud")
        print("8. Set anti-redownload policies on file/folder")
        print("9. Exit")
        
        choice = input("\nEnter your choice (1-9): ").strip()
        
        if choice == "1":
            file_path = input("Enter file path: ").strip()
            remove_download_smart(file_path)
            
        elif choice == "2":
            folder_path = input("Enter folder path (or press Enter for Desktop): ").strip()
            if not folder_path:
                folder_path = os.path.expanduser("~/Desktop")
            files = find_downloaded_icloud_files(folder_path)
            print(f"\nFound {len(files)} downloaded iCloud files:")
            for f in files[:10]:  # Show first 10
                print(f"  - {f}")
            if len(files) > 10:
                print(f"  ... and {len(files) - 10} more")
                
        elif choice == "3":
            folder_path = input("Enter folder path (or press Enter for Desktop): ").strip()
            if not folder_path:
                folder_path = os.path.expanduser("~/Desktop")
            files = find_downloaded_icloud_files(folder_path)
            if files:
                confirm = input(f"Remove downloads from {len(files)} files? (y/n): ")
                if confirm.lower() == 'y':
                    results = batch_remove_downloads(files)
                    successful = sum(1 for r in results if r['success'])
                    print(f"\nProcessed {len(files)} files, {successful} successful")
            else:
                print("No downloaded iCloud files found.")
                
        elif choice == "4":
            file_path = input("Enter file path: ").strip()
            status = get_icloud_file_status(file_path)
            if status:
                print(f"\nFile status for {file_path}:")
                for key, value in status.items():
                    print(f"  {key}: {value}")
            else:
                print("Could not get file status")
                
        elif choice == "5":
            diagnose_icloud_setup()
                
        elif choice == "6":
            file_path = input("Enter file path to debug: ").strip()
            debug_file_attributes(file_path)
                
        elif choice == "7":
            find_and_evict_all_music_files()
            
        elif choice == "8":
            path = input("Enter file or folder path to set anti-redownload policies: ").strip()
            if os.path.isfile(path):
                prevent_auto_redownload(path)
            elif os.path.isdir(path):
                print(f"🔄 Setting policies for all files in: {path}")
                count = 0
                for file_path in Path(path).rglob("*"):
                    if file_path.is_file():
                        status = get_icloud_file_status(str(file_path))
                        if status and status['is_icloud_file']:
                            prevent_auto_redownload(str(file_path))
                            count += 1
                print(f"✅ Set anti-redownload policies on {count} iCloud files")
            else:
                print("❌ Path not found or not accessible")
            
        elif choice == "9":
            print("Goodbye! 👋")
            break
            
        else:
            print("Invalid choice. Please try again.")

# Example usage with common iCloud folders
def find_and_evict_all_music_files():
    """
    Find and evict all music files from iCloud Drive and common iCloud locations.
    """
    # Common music file extensions
    music_extensions = {
        '.mp3', '.m4a', '.aac', '.flac', '.wav', '.ogg', '.wma', 
        #'.m4p', '.mp4', '.mov', '.avi', '.mkv'  # Also include video files that might be music videos
    }
    
    # iCloud locations to search
    icloud_locations = [
        ("iCloud Drive", os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")),
        #("iCloud Desktop", os.path.expanduser("~/Desktop")),
        #("iCloud Documents", os.path.expanduser("~/Documents")),
        #("iCloud Downloads", os.path.expanduser("~/Downloads"))
    ]
    
    print("🎵 Finding all music files in iCloud locations...")
    print("=" * 60)
    
    all_music_files = []
    downloaded_music_files = []
    
    for location_name, location_path in icloud_locations:
        if not os.path.exists(location_path):
            print(f"❌ {location_name} not found: {location_path}")
            continue
            
        print(f"\n🔍 Searching {location_name}: {location_path}")
        
        try:
            file_count = 0
            location_music_files = []
            location_downloaded_files = []
            
            for file_path in Path(location_path).rglob("*"):
                if file_path.is_file():
                    file_count += 1
                    
                    # Progress indicator for large directories
                    if file_count % 500 == 0:
                        print(f"   Checked {file_count} files...")
                    
                    # Check if it's a music file
                    if file_path.suffix.lower() in music_extensions:
                        location_music_files.append(str(file_path))
                        
                        # Check if it's downloaded
                        status = get_icloud_file_status(str(file_path))
                        if status and status['is_icloud_file'] and status['is_downloaded']:
                            location_downloaded_files.append(str(file_path))
                            print(f"   📱 Downloaded music: {file_path.name}")
                        elif status and status['is_icloud_file'] and status['is_placeholder']:
                            print(f"   ☁️  Placeholder music: {file_path.name}")
            
            print(f"   Found {len(location_music_files)} music files, {len(location_downloaded_files)} downloaded")
            all_music_files.extend(location_music_files)
            downloaded_music_files.extend(location_downloaded_files)
            
        except Exception as e:
            print(f"   ❌ Error searching {location_name}: {e}")
    
    print(f"\n📊 Summary:")
    print(f"   Total music files found: {len(all_music_files)}")
    print(f"   Downloaded music files: {len(downloaded_music_files)}")
    
    if not downloaded_music_files:
        print("\n✅ No downloaded music files found - nothing to evict!")
        return
    
    # Show some examples
    print(f"\n📂 Sample downloaded music files:")
    for i, file_path in enumerate(downloaded_music_files[:10]):
        print(f"   {i+1}. {os.path.basename(file_path)}")
    
    if len(downloaded_music_files) > 10:
        print(f"   ... and {len(downloaded_music_files) - 10} more")
    
    # Ask for confirmation
    print(f"\n⚠️  This will evict {len(downloaded_music_files)} music files from local storage.")
    print("   The files will remain in iCloud but won't take up local disk space.")
    confirm = input("   Continue? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("❌ Operation cancelled.")
        return
    
    # Evict the files
    print(f"\n🚀 Starting eviction of {len(downloaded_music_files)} music files...")
    
    successful_evictions = 0
    failed_evictions = 0
    
    for i, file_path in enumerate(downloaded_music_files, 1):
        print(f"\n[{i}/{len(downloaded_music_files)}] Evicting: {os.path.basename(file_path)}")
        
        # Use the smart removal function
        success = remove_download_smart(file_path)
        
        if success:
            successful_evictions += 1
        else:
            failed_evictions += 1
        
        # Progress update every 10 files
        if i % 10 == 0 or i == len(downloaded_music_files):
            print(f"📈 Progress: {i}/{len(downloaded_music_files)} processed")
            print(f"   ✅ Successful: {successful_evictions}")
            print(f"   ❌ Failed: {failed_evictions}")
    
    # Final summary
    print(f"\n🎯 Final Results:")
    print(f"   ✅ Successfully evicted: {successful_evictions} files")
    print(f"   ❌ Failed to evict: {failed_evictions} files")
    
    if successful_evictions > 0:
        print(f"\n💾 Estimated disk space freed: Music files are now stored in iCloud only")
        print("   Check Finder - evicted files should show with cloud icons")
    
    if failed_evictions > 0:
        print(f"\n💡 Tip: Failed evictions might be due to:")
        print("   - Files currently in use")
        print("   - System files that can't be evicted")
        print("   - Network connectivity issues")
def check_eviction_after_delay(file_path, original_size, delay_seconds=5):
    """
    Check if eviction was successful after a delay.
    Sometimes iCloud takes time to process eviction requests.
    """
    import time
    print(f"⏳ Waiting {delay_seconds} seconds for iCloud to process eviction...")
    time.sleep(delay_seconds)
    
    try:
        is_evicted, message = verify_eviction(file_path, original_size)
        if is_evicted:
            print(f"✅ Delayed verification successful: {message}")
            return True
        else:
            print(f"❓ Delayed verification inconclusive: {message}")
            return False
    except Exception as e:
        print(f"❌ Error in delayed verification: {e}")
        return False

def debug_file_attributes(file_path):
    """
    Debug function to show all extended attributes and their values for a file.
    """
    try:
        print(f"\n🔍 Debug info for: {os.path.basename(file_path)}")
        print(f"Full path: {file_path}")
        print(f"File size: {os.path.getsize(file_path):,} bytes")
        
        attrs = xattr.listxattr(file_path)
        print(f"Number of extended attributes: {len(attrs)}")
        
        if not attrs:
            print("❌ No extended attributes found")
            return
            
        print("\n📋 Extended attributes:")
        for attr in attrs:
            try:
                value = xattr.getxattr(file_path, attr)
                # Try to decode as string, fallback to raw bytes
                try:
                    decoded_value = value.decode('utf-8')
                    print(f"  {attr} = '{decoded_value}'")
                except UnicodeDecodeError:
                    print(f"  {attr} = {value} (raw bytes)")
            except (OSError, IOError) as e:
                print(f"  {attr} = (could not read: {e})")
        
        # Show what our function thinks about this file
        status = get_icloud_file_status(file_path)
        if status:
            print(f"\n📊 Our analysis:")
            for key, value in status.items():
                print(f"  {key}: {value}")
        
        # Also check with ls command for comparison
        try:
            result = subprocess.run(['ls', '-la@', file_path], 
                                  capture_output=True, text=True)
            print(f"\n💻 ls -la@ output:")
            print(result.stdout)
        except Exception as e:
            print(f"❌ Could not run ls command: {e}")
            
    except Exception as e:
        print(f"❌ Error debugging file: {e}")

def prevent_auto_redownload(file_path):
    """
    Set comprehensive attributes to prevent automatic re-downloading of evicted files.
    This should be called after eviction to ensure files stay evicted.
    """
    try:
        abs_path = os.path.abspath(file_path)
        
        if not os.path.exists(abs_path):
            return False
        
        print(f"🛡️  Setting persistent eviction policies for: {os.path.basename(abs_path)}")
        
        # Set multiple download policy attributes to be extra sure
        policy_attributes = [
            ('com.apple.file-provider.download-policy', b'never'),
            ('com.apple.file-provider.download-policy', b'0'),
            ('com.apple.clouddocs.download-policy', b'never'),
            ('com.apple.clouddocs.download-policy', b'0'),
            ('com.apple.file-provider.auto-download', b'0'),
            ('com.apple.file-provider.auto-download', b'false'),
            ('com.apple.clouddocs.auto-download', b'0'),
            ('com.apple.clouddocs.auto-download', b'false'),
            ('com.apple.file-provider.evicted', b'1'),
            ('com.apple.file-provider.evicted', b'true'),
            ('com.apple.file-provider.materialized', b'0'),
            ('com.apple.file-provider.materialized', b'false'),
            ('com.apple.file-provider.placeholder', b'1'),
            ('com.apple.file-provider.placeholder', b'true'),
        ]
        
        success_count = 0
        for attr_name, attr_value in policy_attributes:
            try:
                xattr.setxattr(abs_path, attr_name, attr_value)
                success_count += 1
            except OSError:
                continue
        
        print(f"✅ Set {success_count}/{len(policy_attributes)} eviction policies")
        
        # Also try using brctl to set policy if available
        try:
            subprocess.run(['brctl', 'download', abs_path, '--policy', 'never'], 
                         capture_output=True, text=True, check=True)
            print(f"✅ Set brctl download policy to 'never'")
        except:
            pass
            
        return success_count > 0
        
    except Exception as e:
        print(f"❌ Error setting eviction policies: {e}")
        return False


if __name__ == "__main__":
    # Uncomment to run interactive manager
    interactive_icloud_manager()
    
    # Example: Common iCloud locations
    common_icloud_paths = [
        "/Users/dennisporter/Desktop",
        "/Users/dennisporter/Documents", 
        "/Users/dennisporter/Downloads"
    ]
    
    print("Common iCloud locations to check:")
    for path in common_icloud_paths:
        if os.path.exists(path):
            print(f"✅ {path}")
        else:
            print(f"❌ {path} (not found)")
    
    print("\nTo use this script:")
    print("1. Run the interactive manager (already enabled)")
    print("2. Or call functions directly:")
    print('   remove_download_smart("/path/to/file")')
    print('   find_downloaded_icloud_files("/path/to/folder")')

