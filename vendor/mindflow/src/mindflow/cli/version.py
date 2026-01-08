import importlib.metadata


def get_mindflow_version() -> str:
    """Get the version number of MindFlow running the CLI"""
    return importlib.metadata.version("mindflow")


# Legacy alias for compatibility
def get_crewai_version() -> str:
    """Legacy alias for get_mindflow_version()"""
    return get_mindflow_version()
