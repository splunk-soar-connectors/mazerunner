[comment]: # "Auto-generated SOAR connector documentation"
# Cymmetria MazeRunner

Publisher: Cymmetria  
Connector Version: 1\.1\.0  
Product Vendor: Cymmetria  
Product Name: MazeRunner  
Product Version Supported (regex): "\.\*"  
Minimum Product Version: 3\.0\.190  

MazeRunner App

### Configuration Variables
The below configuration variables are required for this Connector to operate.  These variables are specified when configuring a MazeRunner asset in SOAR.

VARIABLE | REQUIRED | TYPE | DESCRIPTION
-------- | -------- | ---- | -----------
**mazerunner\_server** |  required  | string | Server IP/Hostname
**key\_id** |  required  | string | Key ID
**secret** |  required  | string | Secret

### Supported Actions  
[test connectivity](#action-test-connectivity) - Validate the asset configuration for connectivity\.  
[create breadcrumbs](#action-create-breadcrumbs) - Prepare the breadcrumb file for installation  

## action: 'test connectivity'
Validate the asset configuration for connectivity\.

Type: **test**  
Read only: **True**

#### Action Parameters
No parameters are required for this action

#### Action Output
No Output  

## action: 'create breadcrumbs'
Prepare the breadcrumb file for installation

Type: **generic**  
Read only: **True**

#### Action Parameters
No parameters are required for this action

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.data\.msi\_file | string | 
action\_result\.data\.\*\.status | string | 