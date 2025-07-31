# Define variables
$FolderPath = "C:\ProgramData\Physio-Control" # The root folder
$UserName = "crew" # The user or group to add permissions for
$AccessRights = "FullControl" # The desired access rights (e.g., FullControl, Modify, ReadAndExecute)

# Get the current ACL of the root folder
$Acl = Get-Acl $FolderPath

# Create a new FileSystemAccessRule
$AccessRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $UserName,
    $AccessRights,
    "ContainerInherit, ObjectInherit", # Apply to subfolders and files
    "None", # No propagation flags
    "Allow" # Allow or Deny
)

# Add the new access rule to the ACL
$Acl.AddAccessRule($AccessRule)

# Apply the modified ACL to the root folder
Set-Acl -Path $FolderPath -AclObject $Acl