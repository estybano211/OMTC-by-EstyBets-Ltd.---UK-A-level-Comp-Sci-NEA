from tkinter import Frame
from tkinter import font


def fetch_font_settings(root):
    """
    Creates and returns a dictionary of named tkinter Font objects for consistent
    styling across the project.

    Args:
        root: The root Tk window used to bind the font objects.

    Returns:
        dict: A dictionary mapping style names (e.g. 'heading', 'text') to
              tkinter Font instances.
    """
    styles = {
        "title": font.Font(
            root=root, family="Times New Roman", size=35, weight="bold", underline=True
        ),
        "heading": font.Font(
            root=root, family="Arial", size=28, weight="bold", underline=True
        ),
        "subheading": font.Font(root=root, family="Helvetica", size=24, weight="bold"),
        "text": font.Font(root=root, family="Verdana", size=20),
        "button": font.Font(root=root, family="Tahoma", size=18, weight="bold"),
        "terms_and_conditions": font.Font(
            root=root, family="Helvetica", size=20, weight="bold"
        ),
        "emphasis": font.Font(
            root=root, family="Georgia", size=12, weight="bold", slant="italic"
        ),
    }
    return styles


# Default delay for message logging in seconds
DELAY = 1.5


def clear_current_section(self):
    """
    Destroys the currently active section frame if one exists, and resets the
    reference to None.

    Args:
        self: The parent interface object that holds a 'current_section_frame'
              attribute.
    """
    if getattr(self, "current_section_frame", None) is not None:
        self.current_section_frame.destroy()
        self.current_section_frame = None


def set_view(self, view_builder):
    """
    Clears the current section frame and builds a new one using the provided
    view builder function. The new frame is packed into the main frame and
    passed to the view builder.

    Args:
        self: The parent interface object that holds 'main_frame' and
              'current_section_frame' attributes.
        view_builder (callable): A function that accepts a Frame as its sole
                                 argument and populates it with widgets.
    """
    clear_current_section(self)

    self.current_section_frame = Frame(self.main_frame)
    self.current_section_frame.pack(expand=True, fill="both")

    view_builder(self.current_section_frame)
