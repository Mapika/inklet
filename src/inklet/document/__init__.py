"""V2 scientific documents: live definitions, measured layouts and compiled output."""
from .compiler import Document, CompiledFigure, LayoutError, document, subfigure
from .spec import PlotSpec, ComponentSpec, plot_spec, component
from .data import Dataset, DataRef, Source, Series, SharedScale, dataset, shared_scale, CategoryEncoding, FileRef, DerivedData, derive

__all__ = ['Document','CompiledFigure','LayoutError','document','PlotSpec','ComponentSpec',
           'plot_spec','component','Dataset','DataRef','Source','Series','SharedScale','dataset','shared_scale','CategoryEncoding','FileRef','DerivedData','derive']

from .composition import Composition, LayoutValue, composition
from .module import ModuleSpec, module

__all__ += ["subfigure", "Composition", "LayoutValue", "composition", "ModuleSpec", "module"]

from .publication import PublicationProfile, publication
__all__ += ["PublicationProfile", "publication"]
