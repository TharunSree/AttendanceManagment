# This list will be automatically populated by the @nav_item decorator
# as Django loads each of your app's views.py files.
REGISTERED_NAV_ITEMS = []

# The definition of the collapsible groups still lives here.
NAVIGATION_GROUPS = [
{
        'id': 'dashboard',
        'title': 'Dashboard',
        'icon': 'iconsminds-shop-4',
    },
    {
        'id': 'admin_management',
        'title': 'Admin Management',
        'icon': 'iconsminds-gears',
    },
    {
        'id': 'faculty_tools',
        'title': 'Faculty Tools',
        'icon': 'iconsminds-check',
    },
    {
        'id': 'application_settings',  # Unique ID for the group
        'title': 'Application Settings',
        'icon': 'iconsminds-gears',
    },
    {
        'id':'my_academics',
        'title' : 'My Academics',
        'icon' : 'simple-icon-user',
    }
]