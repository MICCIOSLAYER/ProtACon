"""
Copyright (c) 2024 Simone Chiarella

Author: S. Chiarella

Configuration parser.

"""
import configparser
from pathlib import Path


class Config:
    """A class of objects that can read data from a configuration file."""

    def __init__(
        self,
        filename: str,
    ) -> None:
        """
        Contructor of the class.

        Parameters
        ----------
        filename : str
            The name of the configuration file with the values.

        Returns
        -------
        None

        """
        self.config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation())
        self.config.read(Path(__file__).resolve().parent/filename)

    def get_cutoffs(
        self,
    ) -> dict[str, float | int]:
        """
        Return a dictionary with the cutoffs for binarizing the contact map.

        Returns
        -------
        dict[str, float | int]
            The identifier and the cutoffs for the corresponding thresholding.

        """
        return {
            "DISTANCE_CUTOFF": float(
                self.config.get("cutoffs", "DISTANCE_CUTOFF")),
            "POSITION_CUTOFF": int(
                self.config.get("cutoffs", "POSITION_CUTOFF")),
        }

    def get_paths(
        self,
    ) -> dict[str, str]:
        """
        Return a dictionary with the paths to folders to store the files.

        Returns
        -------
        dict[str, str]
            The identifier and the paths to the corresponding folder.

        """
        return {
            "PDB_FOLDER": self.config.get("paths", "PDB_FOLDER"),
            "PLOT_FOLDER": self.config.get("paths", "PLOT_FOLDER"),
        }

    def get_proteins(
        self,
    ) -> dict[str, str | int]:
        """
        Return a dictionary with the codes representing the peptide chains or 

        Returns
        -------
        dict[str, str | int]
            The identifier and the list of protein codes, the max length that a
            protein can have, and the protein sample size.
            

        """
        return {
            "PROTEIN_CODES": self.config.get("proteins", "PROTEIN_CODES"),
            "MAX_LENGTH": int(self.config.get("proteins", "MAX_LENGTH")),
            "SAMPLE_SIZE": int(self.config.get("proteins", "SAMPLE_SIZE")),
        }
