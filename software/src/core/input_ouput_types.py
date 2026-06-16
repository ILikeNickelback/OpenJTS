from enum import Enum


class IOTypes(str, Enum):
    """Enum for input types accepted by the File_browser_win."""
    def __new__(cls, value, dtype, description):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.dtype = dtype
        obj.description = description
        return obj

    TRIGGER = ("trigger", "nan", "Trigger event, no data")
    FILE_PATH = ("file_path", "str", "Path to a file, e.g., image or video")
    FOLDER_PATH = ("folder_path", "str", "Path to a folder")
    FRAME = ("frame", "np.ndarray", "Image frame, typically a numpy array")
    MASK = ("mask", "np.ndarray", "Binary mask, typically a numpy array")
    TEXT = ("text", "str", "Plain text input")
    CMD_DICT = ("cmd_dict", "dict", "Command dictionary")
    CMD_LIST = ("cmd_list", "list", "List of commands")
    STATUS_DICT = ("status_dict", "dict",
                   "Status dictionary with various keys")
    DATALIST = ("datalist", "[[list][list]]",
                "List of X,Y data pairs, e.g., [[0,1,2],[10,20,30]]")
    POSITION = ("position", "int-float", "1D position, e.g., 100 or 100.5")
