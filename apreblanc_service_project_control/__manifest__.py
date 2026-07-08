{
    "name": "Apreblanc Service Project Control",
    "version": "17.0.1.0.0",
    "category": "Project",
    "summary": "Create operational projects from sales orders and control hours",
    "author": "Xtendoo",
    "website": "https://www.xtendoo.es",
    "license": "AGPL-3",
    "depends": [
        "sale_management",
        "project",
        "hr_timesheet",
        "mail",
    ],
    "data": [
        "views/product_template_views.xml",
        "views/sale_order_views.xml",
        "views/project_project_views.xml",
        "views/project_task_views.xml",
    ],
    "installable": True,
    "application": False,
}
