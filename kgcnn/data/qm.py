import os
import numpy as np

from kgcnn.data.base import MemoryGeometricGraphDataset
from kgcnn.utils.adj import add_edges_reverse_indices
from kgcnn.mol.convert import convert_xyz_to_mol_ob, convert_list_to_xyz_str, read_xyz_file, \
    write_mol_block_list_to_sdf, parse_mol_str, dummy_load_sdf_file


class QMDataset(MemoryGeometricGraphDataset):
    r"""This is a base class for 'quantum mechanical' datasets. It generates graph properties from a xyz-file, which
    stores atomic coordinates.

    Additionally, it should be possible to generate approximate chemical bonding information via `openbabel`, if this
    additional package is installed.
    The class inherits :obj:`MemoryGeometricGraphDataset`.

    At the moment, there is no connection to :obj:`MoleculeNetDataset` since usually for geometric data, the usage is
    related to learning quantum properties like energy, orbitals or forces.
    """

    global_proton_dict = {'H': 1, 'He': 2, 'Li': 3, 'Be': 4, 'B': 5, 'C': 6, 'N': 7, 'O': 8, 'F': 9, 'Ne': 10, 'Na': 11,
                          'Mg': 12, 'Al': 13, 'Si': 14, 'P': 15, 'S': 16, 'Cl': 17, 'Ar': 18, 'K': 19, 'Ca': 20,
                          'Sc': 21, 'Ti': 22, 'V': 23, 'Cr': 24, 'Mn': 25, 'Fe': 26, 'Co': 27, 'Ni': 28, 'Cu': 29,
                          'Zn': 30, 'Ga': 31, 'Ge': 32, 'As': 33, 'Se': 34, 'Br': 35, 'Kr': 36, 'Rb': 37, 'Sr': 38,
                          'Y': 39, 'Zr': 40, 'Nb': 41, 'Mo': 42, 'Tc': 43, 'Ru': 44, 'Rh': 45, 'Pd': 46, 'Ag': 47,
                          'Cd': 48, 'In': 49, 'Sn': 50, 'Sb': 51, 'Te': 52, 'I': 53, 'Xe': 54, 'Cs': 55, 'Ba': 56,
                          'La': 57, 'Ce': 58, 'Pr': 59, 'Nd': 60, 'Pm': 61, 'Sm': 62, 'Eu': 63, 'Gd': 64, 'Tb': 65,
                          'Dy': 66, 'Ho': 67, 'Er': 68, 'Tm': 69, 'Yb': 70, 'Lu': 71, 'Hf': 72, 'Ta': 73, 'W': 74,
                          'Re': 75, 'Os': 76, 'Ir': 77, 'Pt': 78, 'Au': 79, 'Hg': 80, 'Tl': 81, 'Pb': 82, 'Bi': 83,
                          'Po': 84, 'At': 85, 'Rn': 86, 'Fr': 87, 'Ra': 88, 'Ac': 89, 'Th': 90, 'Pa': 91, 'U': 92,
                          'Np': 93, 'Pu': 94, 'Am': 95, 'Cm': 96, 'Bk': 97, 'Cf': 98, 'Es': 99, 'Fm': 100, 'Md': 101,
                          'No': 102, 'Lr': 103, 'Rf': 104, 'Db': 105, 'Sg': 106, 'Bh': 107, 'Hs': 108, 'Mt': 109,
                          'Ds': 110, 'Rg': 111, 'Cn': 112, 'Nh': 113, 'Fl': 114, 'Mc': 115, 'Lv': 116, 'Ts': 117,
                          'Og': 118, 'Uue': 119}
    inverse_global_proton_dict = {value: key for key, value in global_proton_dict.items()}

    def __init__(self, data_directory: str = None, dataset_name: str = None, file_name: str = None,
                 verbose: int = 1):
        """Default initialization. Must be called from sub-class.

        Args:
            file_name (str): Filename for reading into memory. This must be the name of the '.xyz' file.
                Default is None.
            data_directory (str): Full path to directory containing all dataset files. Default is None.
            dataset_name (str): Name of the dataset. Important for naming. Default is None.
            verbose (int): Print progress or info for processing, where 0 is silent. Default is 1.
        """
        MemoryGeometricGraphDataset.__init__(self, data_directory=data_directory, dataset_name=dataset_name,
                                             file_name=file_name, verbose=verbose)

    @classmethod
    def _make_mol_list(cls, atoms_coordinates_xyz: list):
        """Make mol-blocks from list of multiple molecules.

        Args:
            atoms_coordinates_xyz (list): Nested list of xyz information for each molecule such as
                `[[['H', 0.0, 0.0, 0.0], ['C', 1.0, 1.0, 1.0], ...], ... ]`

        Returns:
            list: A list of mol-blocks as string.
        """
        mol_list = []
        for x in atoms_coordinates_xyz:
            xyz_str = convert_list_to_xyz_str(x)
            mol_str = convert_xyz_to_mol_ob(xyz_str)
            mol_list.append(mol_str)
        return mol_list

    def prepare_data(self, overwrite: bool = False):
        r"""Pre-computation of molecular structure information from xyz-file.

        Args:
            overwrite (bool): Overwrite existing database mol-json file. Default is False.

        Returns:
            self
        """
        mol_filename = self._get_mol_filename()
        if os.path.exists(os.path.join(self.data_directory, mol_filename)) and not overwrite:
            self._log("INFO:kgcnn: Found rdkit %s of pre-computed structures." % mol_filename)
            return self
        filepath = os.path.join(self.data_directory, self.file_name)
        xyz_list = read_xyz_file(filepath)

        # We need to parallelize this?
        mb = self._make_mol_list(xyz_list)

        write_mol_block_list_to_sdf(mb, os.path.join(self.data_directory, mol_filename))

        return self

    def _get_mol_filename(self):
        """Try to determine a file name for the mol information to store."""
        return "".join(self.file_name.split(".")[:-1]) + ".sdf"

    def read_in_memory(self):
        """Read xyz-file and optionally sdf-file with chemical structure information into memory.

        Returns:
            self
        """
        filepath = os.path.join(self.data_directory, self.file_name)
        xyz_list = read_xyz_file(filepath)
        symbol = [np.array([x[0] for x in y]) for y in xyz_list]
        coords = [np.array([x[1:4] for x in y], dtype="float") for y in xyz_list]
        nodes = [np.array([self.global_proton_dict[x[0]] for x in y], dtype="int") for y in xyz_list]
        self.length = len(symbol)
        self.node_coordinates = coords
        self.node_symbol = symbol
        self.node_number = nodes

        mol_filename = self._get_mol_filename()
        mol_path = os.path.join(self.data_directory, mol_filename)
        if not os.path.exists(mol_path):
            print("WARNING:kgcnn: Can not load sdf-file for dataset %s" % self.dataset_name)
            return self

        # Load sdf file here.
        mol_list = dummy_load_sdf_file(mol_path)
        if mol_list is not None:
            self._log("INFO:kgcnn: Parsing mol information ...", end='', flush=True)
            bond_info = []
            for x in mol_list:
                bond_info.append(np.array(parse_mol_str(x)[5], dtype="int"))
            edge_index = []
            edge_attr = []
            for x in bond_info:
                temp = add_edges_reverse_indices(np.array(x[:, :2]), np.array(x[:, 2:]))
                edge_index.append(temp[0] - 1)
                edge_attr.append(np.array(temp[1], dtype="float"))
            self.edge_indices = edge_index
            self.edge_attributes = edge_attr
            self._log("done")
        return self
