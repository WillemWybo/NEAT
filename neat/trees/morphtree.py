"""
File contains:

    - :class:`MorphLoc`
    - :class:`MorphNode`
    - :class:`MorphTree`

Authors: B. Torben-Nielsen (legacy code) and W. Wybo
"""

import numpy as np

import matplotlib.patheffects as patheffects
import matplotlib.patches as patches
import matplotlib.cm as cm
import matplotlib.pyplot as pl
from mpl_toolkits.axes_grid1 import make_axes_locatable
from mpl_toolkits.mplot3d import Axes3D

import warnings
import copy

from stree import SNode, STree


def originalTreetypeDecorator(fun):
    '''
    Decorator that provides the safety that the treetype is set to
    'original' inside the functions it decorates
    '''
    # wrapper to access self
    def wrapped(self, *args, **kwargs):
        current_treetype = self.treetype
        self.treetype = 'original'
        res = fun(self, *args, **kwargs)
        self.treetype = current_treetype
        return res
    return wrapped

def computationalTreetypeDecorator(fun):
    '''
    Decorator that provides the safety that the treetype is set to
    'computational' inside the functions it decorates. This decorator also
    checks if a computational tree has been defined.

    Raises
    ------
        AttributeError
            If this function is called and no computational tree has been
            defined
    '''
    # wrapper to access self
    def wrapped(self, *args, **kwargs):
        if self._computational_root == None:
            raise AttributeError('No computational tree has been defined, ' + \
                                  'and this function requires one. Use ' + \
                                  ':fun:`MorphTree.setCompTree()`')
        current_treetype = self.treetype
        self.treetype = 'computational'
        res = fun(self, *args, **kwargs)
        self.treetype = current_treetype
        return res
    return wrapped


class MorphLoc(object):
    '''
    Stores a location on the morphology. The location is initialized starting
    from a node and x-value on the real morphology. The location is also be
    stored in the coordinates of the computational morphology. To toggle between
    coordinates, the class stores a reference to the morphology tree on which
    the location is defined, and returns either the original coordinate or the
    coordinate on the computational tree, depending on which tree is active.
    '''

    def __init__(self, loc, reftree, set_as_comploc=False):
        '''
        Initialize an object to specify a location on the morphology. Input is
        either a tuple or a dict where one entry specifies the node index and
        the other entry the x-coordinate specifying the location between parent
        node (x=0) or the node indicated by the index (x=1).

        Parameters
        ----------
            loc: tuple or dict
                if tuple: (node index, x-value)
                if dict: {'node': node index, 'x': x-value}
            reftree: :class:`MorphTree`
            set_as_comploc: bool
                if True, assumes the paremeters provided in `loc` are coordinates
                on the computational tree. Doing this while no computational tree
                has been initialized in `reftree` will result in an error.
                Defaults to False

        Raises
        ------
            ValueError
                If x-coordinate of location is not in ``[0,1]``
        '''
        self.reftree = reftree
        loc = copy.deepcopy(loc)
        if isinstance(loc, tuple):
            x = float(loc[1])
            if x > 1. or x < 0.:
                raise ValueError('x-value should be in [0,1]')
            if set_as_comploc:
                self.comp_loc = {'node': int(loc[0]), 'x': x}
                self._setOriginalLoc()
            else:
                self.loc = {'node': int(loc[0]), 'x': x}
        elif isinstance(loc, dict):
            x = float(loc['x'])
            if x > 1. or x < 0.:
                raise ValueError('x-value should be in [0,1]')
            if set_as_comploc:
                self.comp_loc = loc
                self._setOriginalLoc()
            else:
                self.loc = loc
        elif isinstance(loc, MorphLoc):
            self.__dict__.update(copy.deepcopy(loc.__dict__))
        else:
            raise TypeError('Not a valid location type, should be tuple or dict')

    def __getitem__(self, key):
        if self.reftree.treetype == 'computational':
            try:
                return self.comp_loc[key]
            except AttributeError:
                self._setComputationalLoc()
                return self.comp_loc[key]
        else:
            return self.loc[key]

    def __eq__(self, other_loc):
        if type(other_loc) == dict:
            result = (other_loc['node'] == self.loc['node'])
            if self.loc['node'] != 1:
                result *= np.allclose(other_loc['x'], self.loc['x'])
            return result
        elif type(other_loc) == tuple:
            result = (other_loc[0] == self.loc['node'])
            if self.loc['node'] != 1:
                   result *= np.allclose(other_loc[1], self.loc['x'])
            return result
        elif isinstance(other_loc, MorphLoc):
            result = (other_loc.loc['node'] == self.loc['node'])
            if self.loc['node'] != 1:
                result *= np.allclose(other_loc.loc['x'], self.loc['x'])
            return result
        else:
            return NotImplemented

    def __neq__(self, other_loc):
        result = self.__eq__(other_loc)
        if result is NotImplemented:
            return result
        else:
            return not result

    def __copy__(self):
        '''
        Customization of the copy function so that `loc` and `comp_loc`
        attributes are deep copied and `reftree` attribute still refers to the
        original tree
        '''
        new_loc = type(self)(copy.deepcopy(self.loc), self.reftree)
        if hasattr(self, 'comp_loc'):
            new_loc.__dict__.update({'comp_loc': copy.deepcopy(self.comp_loc)})
        return new_loc

    def __str__(self):
        return str(self.loc)

    def _setComputationalLoc(self):
        if self.loc['node'] != 1:
            current_treetype = self.reftree.treetype
            self.reftree.treetype = 'original'
            node = self.reftree[self.loc['node']]
            # find the computational nodes that are resp. up and down from the node
            node_start = self.reftree._findCompnodeUp(node.parent_node)
            node_stop  = self.reftree._findCompnodeDown(node)
            # length between loc and parent computational node to compute segment
            # length
            L = self.reftree.pathLength({'node': node_start.index, 'x': 1.},
                                         self.loc)
            # get the computational nodes' length
            self.reftree.treetype = 'computational'
            L_cn = self.reftree[node_stop.index].L
            self.reftree.treetype = 'original'
            # set the computational loc
            self.comp_loc = {'node': node_stop.index, 'x': L/L_cn}
            # reset treetype to its former value
            self.reftree.treetype = current_treetype
        else:
            self.comp_loc = copy.deepcopy(self.loc)

    def _setOriginalLoc(self):
        if self.comp_loc['node'] != 1:
            current_treetype = self.reftree.treetype
            self.reftree.treetype = 'computational'
            compnode = self.reftree[self.comp_loc['node']]
            self.reftree.treetype = 'original'
            node = self.reftree[self.comp_loc['node']]
            # find the computational node that is down from the original node
            pcnode = self.reftree._findCompnodeUp(node.parent_node)
            # find the node index and x-coordinate of the original location
            path = self.reftree.pathBetweenNodes(pcnode, node)
            L0 = 0. ; found = False
            for pathnode in path[1:]:
                L1 = L0 + pathnode.L
                Lloc = self.comp_loc['x']*compnode.L
                if Lloc > L0 and Lloc <= L1:
                    self.loc = {'node': pathnode.index,
                                'x': (Lloc-L0) / pathnode.L}
                L0 = L1
            if self.loc['x'] > 1. or self.loc['x'] < 0.:
                raise ValueError('x-value should be in [0,1]')
            # reset treetype to its former value
            self.reftree.treetype = current_treetype
        else:
            self.loc = copy.deepcopy(self.comp_loc)


class MorphNode(SNode):
    '''
    Node associated with :class:`MorphTree`. Stores the geometrical information
    associated with a point on the tree morphology

    Attributes
    ----------
        xyz: numpy.array of floats
            The xyz-coordinates associated with the node
        R: float
            The radius of the node
        swc_type: int
            The type of node, according to the .swc file format convention:
            ``1`` is dendrites, ``2`` is axon, ``3`` is basal dendrite and ``4``
            is apical dendrite.
        L: float
            The length of the node (in micron)
    '''
    def __init__(self, index, p3d=None):
        super(MorphNode, self).__init__(index)
        if p3d != None:
            self.setP3D(*p3d)

    def setP3D(self, xyz, R, swc_type):
        '''
        Set the 3d parameters of the node

        Parameters
        ----------
            xyz: numpy.array
                3D location (um)
            R: float
                Radius of the segment (um)
            swc_type: int
                Type asscoiated with the segment according to SWC standards
        '''
        # morphology parameters
        self.xyz = xyz
        self.R = R
        self.swc_type = swc_type
        # auxiliary variable
        self.used_in_comptree = False

    def setLength(self, L):
        '''
        Set the length of the segment represented by the node

        Parameters
        ----------
            L: float
                the length of the segment (um)
        '''
        self.L = L

    def setRadius(self, R):
        '''
        Set the radius of the segment represented by the node

        Parameters
        ----------
            L: float
                the radius of the segment (um)
        '''
        self.R = R

    def getChildNodes(self, skipinds=(2,3)):
        if self.index == 1:
            return [cnode for cnode in self._child_nodes
                                if cnode.index not in skipinds]
        else:
            return super(MorphNode, self).getChildNodes()

    def setChildNodes(self, cnodes):
        return super(MorphNode, self).setChildNodes(cnodes)

    child_nodes = property(getChildNodes, setChildNodes)


class MorphTree(STree):
    '''
    Subclass of simple tree that implements neuronal morphologies. Reads in
    trees from '.swc' files.

    Can also store a simplified version of the original tree, where only nodes
    are retained that should hold computational parameters - the root, the
    bifurcation nodes and the leafs at least, although the user can also
    specify additional nodes. One tree is set as primary by changing the
    `treetype` attribute (select 'original' for the original morphology and
    'computational' for the computational morphology). Lookup operations will
    often use the primary tree. Using nodes from the other tree for lookup
    operations is unsafe and should be avoided, it is better to set the proper
    tree to primary first.

    Attributes
    ----------
        root: :class:`MorphNode` instance
            The root of the tree.
    '''

    def __init__(self, file_n=None, types=[1,3,4]):
        if file_n != None:
            self.readSwcTreeFromFile(file_n, types=types)
            self._original_root = self.root
        else:
            self._original_root = None
        self._computational_root = None
        self.treetype = 'original' # alternative 'computational'
        # to store sets of locations on the morphology
        self.locs = {}
        self._nids_orig = {}; self._nids_comp = {}
        self._xs_orig = {}; self._xs_comp = {}
        self.d2s = {}
        self.d2b = {}
        self.leafinds = {}

    def __iter__(self, node=None, skip_inds=(2,3)):
        '''
        Overloaded iterator from parent class that avoids iterating over the
        nodes with index 2 and 3

        Parameters
        ----------
            node: :class:`MorphNode`
                The starting node. Defaults to the root
            skip_inds: tuple of ints
                Indices of the nodes that are skipped by the iterator. Defaults
                to ``(2,3)``, the nodes that contain extra geometrical
                information on the soma.

        Yields
        ------
            :class:`MorphNode`
                Nodes in the tree
        '''
        if node == None:
            node = self.root
        if node.index not in skip_inds: yield node
        for cnode in node.getChildNodes():
            for inode in self.__iter__(cnode, skip_inds=skip_inds):
                if node.index not in skip_inds: yield inode

    def getNodes(self, recompute_flag=0, skip_inds=(2,3)):
        '''
        Overloads the parent function to allow skipping nodes with certain
        indices and to return the nodes associated with the corresponding
        `treetype`.

        Parameters
        ----------
            recompute_flag: bool
                whether or not to re-evaluate the node list. Defaults to False.
            skip_inds: tuple of ints
                Indices of the nodes that are skipped by the iterator. Defaults
                to ``(2,3)``, the nodes that contain extra geometrical
                information on the soma.

        Returns
        -------
            list of :class:`MorphNode`
        '''
        if self.treetype == 'original':
            if not hasattr(self, '_nodes_orig') or recompute_flag:
                self._nodes_orig = []
                self._gatherNodes(self.root, self._nodes_orig,
                                   skip_inds=skip_inds)
            return self._nodes_orig
        else:
            if not hasattr(self, '_nodes_comp') or recompute_flag:
                self._nodes_comp = []
                self._gatherNodes(self.root, self._nodes_comp,
                                   skip_inds=skip_inds)
            return self._nodes_comp

    def setNodes(self, illegal):
        raise AttributeError("`nodes` is a read-only attribute")

    nodes = property(getNodes, setNodes)

    def _gatherNodes(self, node, node_list=[], skip_inds=(2,3)):
        '''
        Overloaded gathering function that avoids appending nodes with index 2
        or 3 to the list.

        Parameters
        ----------
            node: :class:`MorphNode`
            node_list: list of :class:`MorphNode`
        '''
        if node.index not in skip_inds: node_list.append(node)
        for cnode in node.getChildNodes():
            self._gatherNodes(cnode, node_list=node_list)

    def getLeafs(self, recompute_flag=0):
        '''
        Overloads the :func:`getLeafs` of the parent class to return the leafs
        in the current `treetype`.

        Parameters
        ----------
            recompute_flag: bool
                Whether to force recomputing the leaf list. Defaults to 0.
        '''
        if self.treetype == 'original':
            if not hasattr(self, '_leafs_orig') or recompute_flag:
                self._leafs_orig = [node for node in self if self.isLeaf(node)]
            return self._leafs_orig
        else:
            if not hasattr(self, '_leafs_comp') or recompute_flag:
                self._leafs_comp = [node for node in self if self.isLeaf(node)]
            return self._leafs_comp

    def setLeafs(self, illegal):
        raise AttributeError("`leafs` is a read-only attribute")

    leafs = property(getLeafs, setLeafs)

    def getNodesInBasalSubtree(self):
        '''
        Return the nodes associated with the basal subtree

        Returns
        -------
            list of :class:`MorphNode`
                List of all nodes in the basal subtree
        '''
        return [node for node in self if node.swc_type in [1,3]]

    def getNodesInApicalSubtree(self):
        '''
        Return the nodes associated with the apical subtree

        Returns
        -------
            list of :class:`MorphNode`
                List of all nodes in the apical subtree
        '''
        return [node for node in self if node.swc_type in [1,4]]

    def getNodesInAxonalSubtree(self):
        '''
        Return the nodes associated with the apical subtree

        Returns
        -------
            list of :class:`MorphNode`
                List of all nodes in the apical subtree
        '''
        return [node for node in self if node.swc_type in [1,2]]

    def setTreetype(self, treetype):
        if treetype == 'original':
            self._treetype = treetype
            self.root = self._original_root
        elif treetype == 'computational':
            if self._computational_root != None:
                self._treetype = treetype
                self.root = self._computational_root
            else:
                raise ValueError('no computational tree has been defined, \
                                `treetype` can only be \'original\'')
        else:
            raise ValueError('`treetype` can be \'original\' or \'computational\'')

    def getTreetype(self):
        return self._treetype

    treetype = property(getTreetype, setTreetype)


    def createCorrespondingNode(self, node_index, p3d):
        '''
        Creates a node with the given index corresponding to the tree class.

        Parameters
        ----------
            node_index: int
                index of the new node
        '''
        return MorphNode(node_index, p3d)

    def readSwcTreeFromFile(self, file_n, types=[1,3,4]):
        '''
        Non-specific for a "tree data structure"
        Read and load a morphology from an SWC file and parse it into
        an :class:`MorphTree` object.

        On the NeuroMorpho.org website, 5 types of somadescriptions are
        considered (http://neuromorpho.org/neuroMorpho/SomaFormat.html).
        The "3-point soma" is the standard and most files are converted
        to this format during a curation step. btmorph follows this default
        specification and the *internal structure of btmorph implements
        the 3-point soma*.

        Parameters
        -----------
        file_n: str
            name of the file to open
        types: list of ints
            NeuroMorpho.org segment types to be included
        '''
        # check soma-representation: 3-point soma or a non-standard representation
        soma_type = self._determineSomaType(file_n)

        file = open(file_n,'r')
        all_nodes = dict()
        for line in file :
            if not line.startswith('#') :
                split = line.split()
                index = int(split[0].rstrip())
                swc_type = int(split[1].rstrip())
                x = float(split[2].rstrip())
                y = float(split[3].rstrip())
                z = float(split[4].rstrip())
                radius = float(split[5].rstrip())
                parent_index = int(split[6].rstrip())
                # create the nodes
                if swc_type in types:
                    p3d = (np.array([x,y,z]), radius, swc_type)
                    node = self.createCorrespondingNode(index, p3d)
                    all_nodes[index] = (swc_type, node, parent_index)

        if soma_type == 1:
            for index, (swc_type, node, parent_index) in all_nodes.items() :
                if index == 1:
                    self.setRoot(node)
                elif index in (2,3):
                    # the 3-point soma representation
                    # (http://neuromorpho.org/neuroMorpho/SomaFormat.html)
                    somanode = all_nodes[1][1]
                    self.addNodeWithParent(node, somanode)
                else:
                    parent_node = all_nodes[parent_index][1]
                    self.addNodeWithParent(node, parent_node)
        # IF multiple cylinder soma representation
        elif soma_type == 2:
            self.setRoot(all_nodes[1][1])

            # get all some info
            soma_cylinders = []
            connected_to_root = []
            for index, (swc_type, node, parent_index) in all_nodes.items() :
                if swc_type == 1 and not index == 1:
                    soma_cylinders.append((node, parent_index))
                    if index > 1 :
                        connected_to_root.append(index)

            # make soma
            s_node_1, s_node_2 = \
                    self._makeSomaFromCylinders(soma_cylinders, all_nodes)

            # add soma
            self._root.R = s_node_1.R
            self.addNodeWithParent(s_node_1,self._root)
            self.addNodeWithParent(s_node_2,self._root)

            # add the other points
            for index, (swc_type, node, parent_index) in all_nodes.items() :
                if swc_type == 1:
                    pass
                else:
                    parent_node = all_nodes[parent_index][1]
                    if parent_node.index in connected_to_root:
                        self.addNodeWithParent(node, self.root)
                    else:
                        self.addNodeWithParent(node, parent_node)

        # set the lengths of the nodes
        for node in self:
            if node.parent_node != None:
                L = np.sqrt(np.sum((node.parent_node.xyz - node.xyz)**2))
            else:
                L = 0.
            node.setLength(L)

        return self

    def _makeSomaFromCylinders(self, soma_cylinders, all_nodes):
        # Construct 3-point soma
        # Step 1: calculate surface of all cylinders
        # Step 2: make 3-point representation with the same surface
        total_surf = 0
        for (node, parent_index) in soma_cylinders:
            nxyz = node.xyz
            pxyz = all_nodes[parent_index][1].xyz
            H = np.sqrt(np.sum((nxyz-pxyz)**2))
            surf = 2*np.pi*p.radius*H
            total_surf = total_surf+surf

        # define apropriate radius
        radius = np.sqrt(total_surf/(4*np.pi))
        rp = self.root.xyz
        rp1 = np.array([rp.x, rp.y - radius, rp.z])
        rp2 = np.array([rp.x, rp.y + radius, rp.z])
        # create the soma nodes
        s_node_1 = self.createCorrespondingNode(2, (rp1, radius, 1))
        s_node_2 = self.createCorrespondingNode(3, (rp2, radius, 1))

        return s_node_1, s_node_2

    def _determineSomaType(self, file_n):
        '''
        Costly method to determine the soma type used in the SWC file.
        This method searches the whole file for soma entries.

        Parameters
        ----------
        file_n: string
            Name of the file containing the SWC description

        Returns
        -------
        soma_type: int
            Integer indicating one of the su[pported SWC soma formats.
            1: Default three-point soma, 2: multiple cylinder description,
            3: otherwise [not suported in btmorph]
        '''
        file = open(file_n, 'r')
        somas = 0
        for line in file:
            if not line.startswith('#') :
                split = line.split()
                index = int(split[0].rstrip())
                s_type = int(split[1].rstrip())
                if s_type == 1 :
                    somas = somas +1
        file.close()
        if somas == 3:
            return 1
        elif somas < 3:
            return 3
        else:
            return 2

    def setCompTree(self, compnodes=[], set_as_primary_tree=0):
        '''
        Sets the nodes that contain computational parameters. This are a priori
        either bifurcations, leafs, the root or nodes where the neurons'
        relevant parameters change.

        Parameters
        ----------
            compnodes: list of :class:`MorphNode`
                list of nodes that should be retained in the computational tree.
                Note that specifying bifurcations, leafs or the root is
                superfluous, since they are part of the computational tree by
                default.
            set_as_primary_tree: bool
                if True, sets the computational tree as the primary tree
        '''
        self.removeComptree()
        compnode_indices = [node.index for node in compnodes]
        nodes = copy.deepcopy(self.nodes)
        for node in nodes:
            if len(node.getChildNodes()) == 1 \
                      and node.parent_node != None \
                      and node.index not in compnode_indices:
                self.removeSingleNode(node)
            elif node.parent_node != None:
                orig_node = self[node.index]
                # orig_bnode, _ = self.upBifurcationNode(orig_node)
                orig_bnode = node.parent_node
                L, R = self.pathLength({'node': orig_bnode.index, 'x': 1.},
                                        {'node': orig_node.index, 'x': 1.},
                                        compute_radius=1)
                node.setLength(L)
                node.setRadius(R)
                node.used_in_comptree = True
                orig_node.used_in_comptree = True
            else:
                orig_node = self[node.index]
                node.used_in_comptree = True
                orig_node.used_in_comptree = True

        self._computational_root = \
                    next(node for node in nodes if node.index == 1)
        if set_as_primary_tree:
            self.treetype = 'computational'
        # create conversion of all coordinate arrays
        for name in self.locs:
            self._storeCompLocs(name)

    def _findCompnodeUp(self, node):
        '''
        !!! Computational tree has to be initialized, otherwise may results in
        error !!!

        If the input node is a node of the original tree, finds the first node
        on the path to the root that has an equivalent in the computational tree.
        If the input node has such an equivalent, it is returned itself.

        If the input node is in the computational tree, returns the node itself.

        Parameters
        ----------
            node: :class:`MorphNode` instance
                the input node

        Returns
        -------
            :class:`MorphNode` instance
        '''
        if not node.used_in_comptree:
            node = self._findCompnodeUp(node.parent_node)
        return node

    def _findCompnodeDown(self, node):
        '''
        !!! Computational tree has to be initialized, otherwise may results in
        error !!!

        If the input node is a node of the original tree, finds the first node
        away from the root that has an equivalent in the computational tree. If
        the input node has such an equivalent, it is returned itself.

        If the input node is in the computational tree, returns the node itself.

        Parameters
        ----------
            node: :class:`MorphNode` instance
                the input node

        Returns
        -------
            :class:`MorphNode` instance
        '''
        if not node.used_in_comptree:
            node = self._findCompnodeDown(node.child_nodes[0])
        return node

    def removeComptree(self):
        '''
        Removes the computational tree
        '''
        self._computational_root = None
        self.treetype = 'original'
        for node in self:
            node.used_in_comptree = False

    def _convertNodeArgToNodes(self, node_arg):
        '''
        Converts a node argument to a list of nodes. Behaviour depends on the
        type of argument.

        If an iterable collection of original nodes is given, and the treetype
        is computational, a reduced list is returned where only the corresponding
        computational nodes are included. If an iterable collection of
        computational nodes is given, and the treetype is original, a list of
        corresponding original nodes is given, but the in between nodes are not
        added.

        Parameters
        ----------
            node_arg: (i) None, (ii) :class:`MorphNode`, (iii) string or (iv) an
                iterable collection of instances of :class:`MorphNode`
                - (i) returns all nodes
                - (ii) returns nodes in the subtree of the given node
                - (iii) string can be 'apical', 'basal' or 'axonal', specifying
                    the subtree that will be returned
                - (iv) returns the same list of nodes

        Returns
        -------
            list of :class:`MorphNode`
        '''
        # convert the input argument to a list of nodes
        if node_arg == None:
            nodes = self.nodes
        elif isinstance(node_arg, MorphNode):
            if self.treetype == 'computational':
                # assure that a list of computational nodes is returned
                node_arg = self._findCompnodeDown(node_arg)
                node_arg = self[node_arg.index]
            else:
                # assure that a list of original nodes is returned
                node_arg = self[node_arg.index]
            nodes = self.gatherNodes(node_arg)
        elif node_arg == 'apical':
            nodes = self.getNodesInApicalSubtree()
        elif node_arg == 'basal':
            nodes = self.getNodesInBasalSubtree()
        elif node_arg == 'axonal':
            nodes = self.getNodesInAxonalSubtree()
        else:
            try:
                nodes = []
                for node in node_arg:
                    assert isinstance(node, MorphNode)
                    if self.treetype == 'computational':
                        # assure that a list of computational nodes is returned
                        node_ = self._findCompnodeDown(node)
                        compnode = self[node_.index]
                        if compnode not in nodes:
                            nodes.append(compnode)
                    else:
                        # assure that a list of original nodes is returned
                        nodes.append(self[node.index])
            except (AssertionError, TypeError):
                raise ValueError('input should be (i) `None`, (ii) an instance of '
                        ':class:`MorphNode`, (iii) one of the following 3 strings '
                        '\'apical\', \'basal\' or \'axonal\' or (iv) an iterable '
                        'collection of instances of :class:MorphNode')

        return nodes

    def pathLength(self, loc1, loc2, compute_radius=0):
        '''
        Find the length of the direct path between loc1 and loc2

        Parameters
        ----------
            loc1: dict, tuple or :class:`MorphLoc`
                one location
            loc2: dict, tuple or :class:`MorphLoc`
                other location
            compute_radius: bool
                if True, also computes the average weighted radius of the path

        Returns
        -------
        L, R (optional)
            L: float
                length of path, in micron
            R: float
                weighted average radius of path, in micron
        '''
        # define location objects
        if type(loc1) == dict or type(loc1) == tuple:
            loc1 = MorphLoc(loc1, self)
        if type(loc2) == dict or type(loc2) == tuple:
            loc2 = MorphLoc(loc2, self)
        # start path length calculation
        if loc1['node'] == loc2['node']:
            node = self[loc1['node']]
            if node.index == 1:
                L = 0. # soma is spherical and has no lenght
            else:
                L = node.L * np.abs(loc1['x'] - loc2['x'])
            if compute_radius:
                R = node.R
        else:
            node1 = self[loc1['node']]
            node2 = self[loc2['node']]
            path1 = self.pathToRoot(node1)[::-1]
            path2 = self.pathToRoot(node2)[::-1]
            path = path1 if len(path1) < len(path2) else path2
            ind = next((ii for ii in xrange(len(path)) if path1[ii] != path2[ii]),
                       len(path))
            if path1[ind-1] == node1:
                L  = node1.L * (1. - loc1['x'])
                L += sum(node.L for node in path2[ind:-1])
                L += node2.L * loc2['x']
                if compute_radius:
                    R  = node1.R * node1.L * (1. - loc1['x'])
                    R += sum(node.R * node.L for node in path2[ind:-1])
                    R += node2.R * node2.L * loc2['x']
                    R /= L
            elif path2[ind-1] == node2:
                L  = node1.L * loc1['x']
                L += sum(node.L for node in path1[ind:-1])
                L += node2.L * (1. - loc2['x'])
                if compute_radius:
                    R  = node1.R * node1.L * loc1['x']
                    R += sum(node.R * node.L for node in path2[ind:-1])
                    R += node2.R * node2.L * (1. - loc2['x'])
                    R /= L
            else:
                L  = node1.L * loc1['x']
                L += sum(node.L for node in path1[ind:-1])
                L += sum(node.L for node in path2[ind:-1])
                L += node2.L * loc2['x']
                if compute_radius:
                    R  = node1.R * node1.L * loc1['x']
                    R += sum(node.R * node.L for node in path1[ind:-1])
                    R += sum(node.R * node.L for node in path2[ind:-1])
                    R += node2.R * node2.L * loc2['x']
                    R /= L
        if compute_radius:
            return L, R
        else:
            return L

    @originalTreetypeDecorator
    def storeLocs(self, locs, name):
        '''
        Store locations under a specified name

        Parameters
        ----------
            locs: list of dicts, tuples or :class:`MorphLoc`
                the locations to be stored
            name: string
                name under which these locations are stored

        Raises
        ------
            ValueError
                If multiple locations are on the soma.
        '''
        # copy list and store in MorphLoc if necessary
        locs_ = []
        n1 = 0
        for loc in locs:
            if type(loc) == dict or type(loc) == tuple:
                locs_.append(MorphLoc(loc, self))
            else:
                locs_.append(copy.copy(loc))
            if locs_[-1]['node'] == 1: n1 += 1
        if n1 > 1:
            raise ValueError('There can only be one location on the soma, \
                             multiple soma location occur in input')
        self.locs[name] = locs_
        self._nids_orig[name] = np.array([loc['node'] for loc in locs_])
        self._xs_orig[name] = np.array([loc['x'] for loc in locs_])
        if self._computational_root != None:
            self._storeCompLocs(name)

    @computationalTreetypeDecorator
    def _storeCompLocs(self, name):
        self._nids_comp[name] = np.array([loc['node'] for loc in self.locs[name]])
        self._xs_comp[name] = np.array([loc['x'] for loc in self.locs[name]])

    def removeLocs(self, name):
        '''
        Remove a set of locations of a given name

        Parameters
        ----------
            name: string
                name under which the desired list of locations is stored
        '''
        try:
            del self.locs[name]
            del self._nids_orig[name]
            del self._nids_comp[name]
            del self._xs_orig[name]
            del self._xs_comp[name]
        except KeyError:
            warnings.warn('Locations of name %s were not defined'%name)
        try:
            del self.d2s[name]
        except KeyError: pass
        try:
            del self.d2b[name]
        except KeyError: pass
        try:
            del self.leafinds[name]
        except KeyError: pass

    def _tryName(self, name):
        '''
        Tests if the name is in use. Raises a KeyError when it is not in use and
        prints a list of possible names

        Parameters
        ----------
            name: string
                name of the desired list of locations

        Raises
        ------
            KeyError
                If 'name' does not refer to a set of locations in use
        '''
        try:
            self.locs[name]
        except KeyError as err:
            err.args = ('\'' + err.args[0] \
                             + '\' name not in use. Possible names are ' \
                             + str(self.locs.keys()),)
            raise

    def getLocs(self, name):
        '''
        Returns a set of locations of a specified name

        Parameters
        ----------
            name: string
                name under which the desired list of locations is stored

        Returns
        -------
            list of :class:`MorphLoc`
        '''
        self._tryName(name)
        return self.locs[name]

    def getNodeIndices(self, name):
        '''
        Returns an array of nodes of locations of a specified name

        Parameters
        ----------
            name: string
                name under which the desired list of locations is stored

        Returns
        -------
            numpy.array of ints
        '''
        self._tryName(name)
        return self.nids[name]

    def getNids(self):
        if self.treetype == 'original':
            return self._nids_orig
        else:
            return self._nids_comp

    def setNids(self, nids):
        if self.treetype == 'original':
            self._nids_orig = nids
        else:
            self._nids_comp = nids

    nids = property(getNids, setNids)

    def getXCoords(self, name):
        '''
        Returns an array of x-values of locations of a specified name

        Parameters
        ----------
            name: string
                name under which the desired list of locations is stored
        '''
        self._tryName(name)
        return self.xs[name]

    def getXs(self):
        if self.treetype == 'original':
            return self._xs_orig
        else:
            return self._xs_comp

    def setXs(self, xs):
        if self.treetype == 'original':
            self._xs_orig = xs
        else:
            self._xs_comp = xs

    xs = property(getXs, setXs)

    def getLocindsOnNode(self, name, node):
        '''
        Returns a list of the indices of locations in the list of a given name
        that are on a the input node, ordered for increasing x

        Parameters
        ----------
            name: string
                which list of locations to consider
            node: :class:`MorphNode`
                the node to consider. When node, should be part of the original
                tree
        Returns
        -------
            list of ints
                indices of locations on the path
        '''
        self._tryName(name)
        nids = self.nids[name]
        xs = self.xs[name]
        # get the locinds on the node
        inds = np.where(nids == node.index)[0]
        sortinds = np.argsort(xs[inds])

        return inds[sortinds].tolist()

    def getLocindsOnNodes(self, name, node_arg):
        '''
        Returns a list of the indices of locations in the list of a given name
        that are on one of the nodes specified in the node list. Within each
        node, locations are ordered for increasing x

        Parameters
        ----------
            name: string
                which list of locations to consider
            node_arg:
                see documentation of :func:`MorphTree._convertNodeArgToNodes`
        Returns
        -------
            list of ints
                indices of locations on the path
        '''
        # find locinds on all nodes
        locinds = []
        for node in self._convertNodeArgToNodes(node_arg):
            locinds.extend(self.getLocindsOnNode(name, node))

        return locinds

    def getLocindsOnPath(self, name, node0, node1, xstart=0., xstop=1.):
        '''
        Returns a list of the indices of locations in the list of a given name
        that are on the given path. The path is taken to start at the input
        x-start coordinate of the first node in the list and to stop at the
        given x-stop coordinate of the last node in the list

        Parameters
        ----------
            name: string
                which list of locations to consider
            node0: :class:`SNode`
                start node of path
            node1: :class:`SNode`
                stop node of path
            xstart: float (in ``[0,1]``)
                starting coordinate on `node0`
            xstop: float (in ``[0,1]``)
                stopping coordinate on `node1`

        Returns
        -------
            list of ints
                Indices of locations on the path. If path is empty, an empty
                array is returned.
        '''
        self._tryName(name)
        locs = self.locs[name]
        xs = self.xs[name]
        # find the path
        path = self.pathBetweenNodes(node0, node1)
        # find the location indices
        locinds = []
        if len(path) > 1:
            # first node in path
            node = path[0]
            ninds = np.array(self.getLocindsOnNode(name, node)).astype(int)
            if node.parent_node == None:
                locinds.extend(ninds)
            else:
                if node.parent_node == path[1]:
                    # goes runs towards root
                    inds = np.where(xs[ninds] <= xstart)[0]
                    sortinds = np.argsort(xs[ninds][inds])[::-1]
                else:
                    # path goes away from root
                    inds = np.where(xs[ninds] >= xstart)[0]
                    sortinds = np.argsort(xs[ninds][inds])
                locinds.extend(ninds[inds][sortinds])
            # middle nodes in path
            for ii, node in enumerate(path[1:-1]):
                ninds = np.array(self.getLocindsOnNode(name, node)).astype(int)
                if node.parent_node == None:
                    locinds.extend(ninds)
                elif path[ii+2] == node.parent_node:
                    # path goes towards root
                    sortinds = np.argsort(xs[ninds])
                    locinds.extend(ninds[sortinds[::-1]])
                elif path[ii] == node.parent_node:
                    # path goes away from root
                    sortinds = np.argsort(xs[ninds])
                    locinds.extend(ninds[sortinds])
                else:
                    # turning point (path only goes on this node at x=1)
                    inds = np.where((1. - xs[ninds]) < 1e-4)[0]
                    if len(inds) > 0:
                        locinds.extend(ninds[inds])
            # last node in path
            node = path[-1]
            ninds = np.array(self.getLocindsOnNode(name, node)).astype(int)
            if node.parent_node == None:
                locinds.extend(ninds)
            else:
                if node.parent_node  == path[-2]:
                    # path goes away from root
                    inds = np.where(xs[ninds] <= xstop)[0]
                    sortinds = np.argsort(xs[ninds][inds])
                else:
                    # path goes towards root
                    inds = np.where(xs[ninds] >= xstop)[0]
                    sortinds = np.argsort(xs[ninds][inds])[::-1]
                locinds.extend(ninds[inds][sortinds])
        elif len(path) == 1:
            node = path[0]
            ninds = np.array(self.getLocindsOnNode(name, node)).astype(int)
            if node.parent_node == None:
                locinds.extend(ninds)
            else:
                if xstart < xstop:
                    inds = np.where(np.logical_and(xs[ninds]>=xstart, xs[ninds]<=xstop))[0]
                    sortinds = np.argsort(xs[ninds][inds])
                else:
                    inds = np.where(np.logical_and(xs[ninds]>=xstop, xs[ninds]<=xstart))[0]
                    sortinds = np.argsort(xs[ninds][inds])[::-1]
                locinds.extend(ninds[inds][sortinds])

        return locinds

    def getNearestLocinds(self, locs, name, direction=0, pprint=False):
        '''
        For each location in the input location list, find the index of the
        closest location in a set of locations stored under a given name. The
        search can go in the either go in the up or down direction or in both
        directions.

        Parameters
        ----------
            locs: list of dicts, tuples or :class:`MorphLoc`
                the locations for which the nearest location index has to be
                found
            name: string
                name under which the reference list is stored
            direction: int
                flag to indicate whether to search in both directions (0), only
                in the up direction (1) or in the down direction (2).

        Returns
        -------
            loc_indices: list of ints
                indices of the locations closest to the given locs
        '''
        self._tryName(name)
        # create the locs in a desirable format
        locs_ = []
        for loc in locs:
            if type(loc) == dict or type(loc) == tuple:
                locs_.append(MorphLoc(loc, self))
            else:
                locs_.append(copy.deepcopy(loc))
        locs = locs_
        # look for the location indices
        loc_indices = []
        for loc in locs:
            loc_ind1 = None; loc_ind2 = None
            # find the location indices if necessary
            if direction == 0 or direction == 1:
                loc_ind1 = self._findLocsDown(loc, name)
            if direction == 0 or direction == 2:
                loc_ind2 = self._findLocsUp(loc, name)
            # save the index of the closest location, if it exists and
            # if it is asked for
            if loc_ind1 == None and (direction == 0 or direction == 2):
                loc_indices.append(loc_ind2)
            elif loc_ind2 == None and (direction == 0 or direction == 1):
                loc_indices.append(loc_ind1)
            else:
                L1 = self.pathLength(loc, self.locs[name][loc_ind1])
                L2 = self.pathLength(loc, self.locs[name][loc_ind2])
                if L1 >= L2:
                    loc_indices.append(loc_ind2)
                else:
                    loc_indices.append(loc_ind1)
        return loc_indices

    def _findLocsUp(self, loc, name):
        look_further = False
        # look if there are locs on the same node
        n_inds = np.where(loc['node'] == self.nids[name] )[0]
        if len(n_inds) > 0:
            if loc['node'] == 1:
                loc_ind = n_inds[0]
            else:
                x_inds = np.where(loc['x'] <= self.xs[name][n_inds])[0]
                if len(x_inds) != 0:
                    loc_ind = n_inds[x_inds[0]]
                else:
                    look_further = True
        else:
            look_further = True
        # if no locs on the same node, then proceed to child nodes
        # else, return the smallest location larger than loc
        if look_further:
            node = self[loc['node']]
            cnodes = node.getChildNodes()
            loc_inds = []
            for cnode in cnodes:
                cloc_ind = self._findLocsUp({'node': cnode.index, 'x': 0.}, name)
                if cloc_ind != None:
                    loc_inds.append(cloc_ind)
            # get the one that is closest, if they exist
            pl_aux = 1e4
            ind_loc = 0
            for i, l_i in enumerate(loc_inds):
                pl = self.pathLength({'node': loc['node'], 'x': 1.}, self.locs[name][l_i])
                if pl < pl_aux:
                    pl_aux = pl
                    ind_loc = i
            if pl_aux > 0. and len(loc_inds) > 0:
                loc_ind = loc_inds[ind_loc]
            elif pl_aux == 0. and node.index == 1:
                loc_ind = loc_inds[ind_loc]
            else:
                loc_ind = None
        return loc_ind

    def _findLocsDown(self, loc, name):
        look_further = False
        # look if there are locs on the same node
        n_inds = np.where(loc['node'] == self.nids[name] )[0]
        if len(n_inds) > 0:
            if loc['node'] == 1:
                loc_ind = n_inds[0]
            else:
                x_inds = np.where(loc['x'] >= self.xs[name][n_inds])[0]
                if len(x_inds) != 0:
                    loc_ind = n_inds[x_inds[-1]]
                else:
                    look_further = True
        else:
            look_further = True
        if look_further:
            # if no locs on the same node, then proceed to resp. parent and child nodes
            node = self[loc['node']]
            pnode = node.getParentNode()
            loc_inds = []
            # check parent node
            if pnode != None:
                ploc_ind = self._findLocsDown({'node': pnode.index, 'x': 1.}, name)
                if ploc_ind != None:
                    loc_inds.append(ploc_ind)
            # check other child nodes of parent node
            if pnode != None:
                ocnodes = copy.copy(pnode.getChildNodes())
                ocnodes.remove(node)
            else:
                ocnodes = []
            for cnode in ocnodes:
                cloc_ind = self._findLocsUp({'node': cnode.index, 'x': 0.}, name)
                if cloc_ind != None:
                    loc_inds.append(cloc_ind)
            # get the one that is closest, if they exist
            pl_aux = 1e4
            ind_loc = 0
            for i, l_i in enumerate(loc_inds):
                pl = self.pathLength({'node': loc['node'], 'x': 1.}, self.locs[name][l_i])
                if pl < pl_aux:
                    pl_aux = pl
                    ind_loc = i
            if pl_aux > 0. and len(loc_inds) > 0:
                loc_ind = loc_inds[ind_loc]
            else:
                loc_ind = None
        return loc_ind

    def getLeafLocinds(self, name):
        '''
        Find the indices in the desire location list that are 'leafs', i.e.
        locations for which no other location exist that is farther from the
        root

        Parameters
        ----------
            name: string
                name of the desired set of locations

        Returns
        -------
            list of inds
                the indices of the 'leaf' locations
        '''
        try:
            self.leafinds[name]
        except KeyError:
            self._tryName(name)
            self.leafinds[name] = []
            locs = self.locs[name]
            for ind, loc in enumerate(locs):
                if not self._hasLocUp(loc, name):
                    self.leafinds[name].append(ind)
        return self.leafinds[name]

    def _hasLocUp(self, loc, name):
        look_further = False
        # look if there are locs on the same node
        if loc['node'] != 1:
            n_inds = np.where(loc['node'] == self.nids[name] )[0]
            if len(n_inds) > 0:
                x_inds = np.where(loc['x'] < self.xs[name][n_inds])[0]
                if len(x_inds) > 0:
                    returnbool = True
                else:
                    look_further = True
            else:
                look_further = True
        else:
            look_further = True
        # if no locs on the same node, then proceed to child nodes
        if look_further:
            node = self[loc['node']]
            cnodes = node.child_nodes
            returnbool = False
            for cnode in cnodes:
                if self._hasLocUp({'node': cnode.index, 'x': 0.}, name):
                    returnbool = True
        return returnbool

    def distancesToSoma(self, name):
        '''
        Compute the distance of each location in a given set to the soma

        Parameters
        ----------
            name: string
                name of the set of locations

        Returns
        -------
            numpy.array of floats
                the distances to the soma of the corresponding locations
        '''
        try:
            return self.d2s[name]
        except KeyError:
            self._tryName(name)
            locs = self.locs[name]
            self.d2s[name] = np.array([self.pathLength({'node': 1, 'x': 0.}, loc) \
                                        for loc in locs])
            return self.d2s[name]

    def distancesToBifurcation(self, name):
        '''
        Compute the distance of each location to the nearest bifurcation in
        the direction of the root

        Parameters
        ----------
            name: string
                name of the set of locations

        Returns
        -------
            numpy.array of floats
                the distances to the nearest bifurcation of the corresponding
                locations
        '''
        try:
            return self.d2b[name]
        except KeyError:
            self._tryName(name)
            self.d2b[name] = []
            locs = self.locs[name]
            for i, loc in enumerate(locs):
                if loc['node'] != 1:
                    if loc['node'] != locs[i-1]['node']:
                        node = self[loc['node']]
                        bnode, _ = self.upBifurcationNode(node)
                    self.d2b[name].append(self.pathLength( \
                                          {'node': bnode.index, 'x': 1.}, loc))
                else:
                    self.d2b[name].append(0.)
            return self.d2b[name]

    def distributeLocsOnNodes(self, d2s, node_arg=None, name='No'):
        '''
        Distributes locs on a given set of nodes at specified distances from the
        soma. If the specified distances are on the specified nodes, the list
        of locations will be empty. The locations are stored if the name is set
        to be something other than 'No'. On each node, locations are ordered from
        low to high x-values.

        Parameters
        ----------
            d2s: numpy.array of floats
                the distances from the soma at which to put the locations (micron)
            node_arg:
                see documentation of :func:`MorphTree._convertNodeArgToNodes`
            name: string
                the name under which the locations are stored. Defaults to 'No'
                which means the locations are not stored

        Returns
        -------
            list of :class:`MorphLoc`
                the list of locations
        '''
        # distribute the locations
        locs = []
        for node in self._convertNodeArgToNodes(node_arg):
            if node.parent_node != None:
                L0 = self.pathLength({'node': 1, 'x': 0.5},
                                      {'node': node.index, 'x': 0.})
                L1 = self.pathLength({'node': 1, 'x': 0.5},
                                      {'node': node.index, 'x': 1.})
                inds = np.where(np.logical_and(L0 < d2s, d2s <= L1))[0]
                Ls = np.sort(d2s[inds])
                locs.extend([MorphLoc((node.index, (L-L0)/(L1-L0)), self) \
                                        for L in Ls if L > 1e-12])
            elif np.any(np.abs(d2s) <= 1e-12):
                # node is soma, append a location on the soma
                locs.append(MorphLoc((node.index, 0.5), self))
        if name != 'No': self.storeLocs(locs, name=name)
        return locs

    @computationalTreetypeDecorator
    def distributeLocsUniform(self, dx, node_arg=None, name='No'):
        '''
        Distributes locations as uniform as possible, i.e. for a given distance
        between locations `dx`, locations are distributed equidistantly on each
        given node in the computational tree so that and their amount is computed
        so that the distance in between them is as close to `dx` as possible.
        Depth-first ordering.

        Parameters
        ----------
            dx: float (> 0)
                target distance in micron between the locations
            node_arg:
                see documentation of :func:`MorphTree._convertNodeArgToNodes`
            name: string
                the name under which the locations are stored. Defaults to 'No'
                which means the locations are not stored

        Returns
        -------
            list of :class:`MorphLoc`
                the list of locations
        '''
        assert dx > 0
        # distribute the locations
        locs = []
        for node in self._convertNodeArgToNodes(node_arg):
            if node.parent_node == None:
                locs.append(MorphLoc((node.index, 0.5), self,
                                     set_as_comploc=True))
            else:
                Nloc = np.round(node.L / dx)
                xvals = np.arange(1, Nloc+1) / float(Nloc)
                locs.extend([MorphLoc((node.index, xv), self,
                                      set_as_comploc=True) for xv in xvals])
        if name != 'No': self.storeLocs(locs, name=name)
        return locs

    def distributeLocsRandom(self, num, dx=0.001, node_arg=None,
                                add_soma=1, name='No'):
        '''
        Returns a list of input locations randomly distributed on the tree

        Parameters
        ----------
            num: int
                number of inputs
            dx: float
                minimal or given distance between input locations (micron)
            node_arg:
                see documentation of :func:`MorphTree._convertNodeArgToNodes`
            name: string
                the name under which the locations are stored. Defaults to 'No'
                which means the locations are not stored

        output:
            - [inlocs]: list of dictionnaries representing inlocs.
        '''
        # use the requested subset of nodes
        nodes = [node for node in self._convertNodeArgToNodes(node_arg)
                 if node.index != 1]
        # initialize the loclist with or without soma
        if add_soma:
            locs = [{'node': 1, 'x': 0.}]
        else:
            locs = []
        # add the nodes
        for ii in xrange(num):
            nodes_left = [node.index for node in nodes
                            if 'tag' not in node.content]
            if len(nodes_left) < 1:
                break
            index = np.random.choice(nodes_left)
            x = np.random.random()
            locs.append(MorphLoc((index, x), self))
            node = self[index]
            self._tagNodesDown(node, node, dx=dx)
            self._tagNodesUp(node, node, dx=dx)
        self._removeTags()
        # store the locations
        if name != 'No': self.storeLocs(locs, name=name)
        return locs

    def _tagNodesDown(self, start_node, node, dx=0.001):
        if 'tag' not in node.content:
            if node.index == start_node.index:
                length = 0.
            else:
                length = self.pathLength({'node': start_node.index, 'x': 1.},
                                          {'node': node.index, 'x': 0.})
            if length < dx:
                node.content['tag'] = 1
                for cnode in node.child_nodes:
                    self._tagNodesDown(start_node, cnode, dx=dx)

    def _tagNodesUp(self, start_node, node, cnode=None, dx=0.001):
        if node.index == start_node.index:
            length = 0.
        else:
            length = self.pathLength({'node': start_node.index, 'x': 1.},
                                      {'node': node.index, 'x': 1.})
        if length < dx:
            node.content['tag'] = 1
            cnodes = node.child_nodes
            if len(cnodes) > 1:
                if cnode != None:
                    cnodes = list(set(cnodes) - set([cnode]))
                for cn in cnodes:
                    self._tagNodesDown(start_node, cn, dx=dx)
            pnode = node.getParentNode()
            if pnode != None:
                self._tagNodesUp(start_node, pnode, node, dx=dx)

    def _removeTags(self):
        for node in self:
            if 'tag' in node.content:
                del node.content['tag']

    def makeXAxis(self, dx, node_arg=None):
        '''
        Create a set of locs suitable for serving as the x-axis for 1D plotting.
        The neurons is put on a 1D axis with a depth-first ordering.

        Parameters
        ----------
            dx: float
                target separation between the plot points (micron)
            node_arg:
                see documentation of :func:`MorphTree._convertNodeArgToNodes`
                The nodes on which the locations for the x-axis are distributed.
                When this is given as a list of nodes, assumes a depth first
                ordering.
        '''
        # if comptree has not been set, create a basic one for plotting
        if self._computational_root == None:
            self.setCompTree()
        # distribute the x-axis locations
        self.distributeLocsUniform(dx, node_arg=node_arg, name='xaxis')
        # get the root node
        nodes = self._convertNodeArgToNodes(node_arg)
        # check that first node is root
        for node in nodes:
            if nodes[0] in node.child_nodes:
                raise ValueError('Input `node_arg` is not a depth-first ordered'
                                 ' list of nodes.')
        # set the node colors for both trees
        if self.treetype == 'original':
            rootnode_orig = nodes[0]
            tempnode = self._findCompnodeDown(nodes[0])
            self.setNodeColors(rootnode_orig)
            self.treetype = 'computational'
            rootnode_comp = self[tempnode.index]
            self.setNodeColors(rootnode_comp)
            self.treetype = 'original'
        else:
            rootnode_comp = nodes[0]
            self.setNodeColors(rootnode_comp)
            self.treetype = 'original'
            rootnode_orig = self[rootnode.comp.index]
            self.setNodeColors(rootnode_orig)
            self.treetype = 'computational'
        # compute the x-axis 1D array
        pinds = self.getLeafLocinds('xaxis')
        d2s = self.distancesToSoma('xaxis')
        xaxis = d2s[0:pinds[0]+1].tolist()
        d_add = d2s[pinds[0]]
        for ii in xrange(0,len(pinds)-1):
            xaxis.extend((d_add + d2s[pinds[ii]+1:pinds[ii+1]+1] \
                            - d2s[pinds[ii]+1]).tolist())
            d_add += d2s[pinds[ii+1]] - d2s[pinds[ii]+1]
        self.xaxis = np.array(xaxis)

    def setNodeColors(self, startnode=None):
        '''
        Set the color code for the nodes for 1D plotting

        Parameters
        ----------
            node: int or :class:`MorphNode`
                index of the node or node whose subtree will be colored. Defaults
                to the root
        '''
        if startnode == None: startnode = self.root
        for node in self: node.content['color'] = 0.
        self.node_color = [0.] # trick to pass the pointer and not the number itself
        self._setColorsDown(startnode)

    def _setColorsDown(self, node):
        node.content['color'] = self.node_color[0]
        if self.isLeaf(node):
            self.node_color[0] += 1.
        for cnode in node.child_nodes:
            self._setColorsDown(cnode)

    def getXValues(self, locs):
        '''
        Get the corresponding location on the x-axis of the input locations

        Parameters
        ----------
            locs: list of tuples, dicts or :class:`MorphLoc`
                list of the locations
        '''
        locinds = np.array(self.getNearestLocinds(locs, 'xaxis')).astype(int)
        return self.xaxis[locinds]

    def plot1D(self, ax, parr, *args, **kwargs):
        '''
        Plot an array where each element corresponds to the matching location on
        the x-axis with a depth-first ordering on a 1D plot

        Parameters
        ----------
            ax: :class:`matplotlib.axes.Axes` instance
                the ax object on which the plot will be made
            parr: numpy.array of floats
                the array that will be plotted
            args, kwargs:
                arguments for :func:`matplotlib.pyplot.plot`

        Returns
        -------
            lines: list of :class:`matplotlib.lines.Line2D` instances
                the line segments corresponding to the value of the plotted array
                in each branch

        Raises
        ------
            AssertionError
                When the number of elements in the data array in not equal to
                the number of elements on the x-axis
        '''
        assert len(parr) == len(self.locs['xaxis'])
        pinds = self.getLeafLocinds('xaxis')
        d2s = self.distancesToSoma('xaxis')
        # make the plot
        lines = []
        line = ax.plot(self.xaxis[0:pinds[0]+1], parr[0:pinds[0]+1],
                       *args, **kwargs)
        lines.append(line[0])
        if 'label' in kwargs.keys():
            kwargs = copy.deepcopy(kwargs)
            del kwargs['label']
        for ii in xrange(0,len(pinds)-1):
            line = ax.plot(self.xaxis[pinds[ii]+1:pinds[ii+1]+1],
                            parr[pinds[ii]+1:pinds[ii+1]+1],
                            *args, **kwargs)
            lines.append(line[0])
        return lines

    def setLineData(self, lines, parr):
        '''
        Update the line objects with new data

        Parameters
        ----------
            lines: list of :class:`matplotlib.lines.Line2D` instance
                the line segments of which the data has to be updated
            parr: numpy.array of floats
                the array that will be put in the line segments

        Raises
        ------
            AssertionError
                When the number of elements in the data array in not equal to
                the number of elements on the x-axis
        '''
        assert len(parr) == len(self.locs['xaxis'])
        pinds = self.getLeafLocinds('xaxis')
        d2s = self.distancesToSoma('xaxis')
        lines[0].set_data(self.xaxis[0:pinds[0]+1], parr[0:pinds[0]+1])
        for ii in xrange(0,len(pinds)-1):
            ll = ii+1
            lines[ll].set_data(self.xaxis[pinds[ii]+1:pinds[ii+1]+1],
                                parr[pinds[ii]+1:pinds[ii+1]+1])

    def plotTrueD2S(self, ax, parr, cmap=None, **kwargs):
        '''
        Plot an array where each element corresponds to the matching location in
        the x-axis location list. Now all locations are plotted at their true
        distance from the soma.

        Parameters
        ----------
            ax: :class:`matplotlib.axes.Axes` instance
                the ax object on which the plot will be made
            parr: numpy.array of floats
                the array that will be plotted
            cmap: :class:`matplotlib.colors.Colormap` instance
                If provided, the lines will be colored according to the branch
                to which they belong, in colors specified by the colormap
            args, kwargs:
                arguments for :func:`matplotlib.pyplot.plot`

        Returns
        -------
            lines
            lines: list of :class:`matplotlib.lines.Line2D`
                the line segments corresponding to the value of the plotted array
                in each branch

        Raises
        ------
            AssertionError
                When the number of elements in the data array in not equal to
                the number of elements on the x-axis
        '''
        assert len(parr) == len(self.locs['xaxis'])
        locs = self.locs['xaxis']
        pinds = self.getLeafLocinds('xaxis')
        d2s = self.distancesToSoma('xaxis')
        # list of colors for plotting
        cs = {node.index: node.content['color'] for node in self}
        cplot = [cs[loc['node']] for loc in locs]
        max_cs = max(cplot)
        min_cs = min(cplot)
        if np.abs(max_cs - min_cs) < 1e-12:
            norm_cs = max_cs + 1e-2
        else:
            norm_cs = (max_cs - min_cs) * (1. + 1./100.)
        # create the truespace plot
        lines = []
        if cmap != None:
            kwargs['c'] = cmap((cplot[0]-min_cs)/norm_cs)
            if 'color' in kwargs: del kwargs['color']
        line = ax.plot(d2s[0:pinds[0]+1], parr[0:pinds[0]+1], **kwargs)
        lines.append(line[0])
        if 'label' in kwargs: del kwargs['label']
        for ii in xrange(0,len(pinds)-1):
            if cmap != None:
                kwargs['c'] = cmap((cs[locs[pinds[ii]+1]['node']]-min_cs)/norm_cs)
            line = ax.plot(d2s[pinds[ii]+1:pinds[ii+1]+1],
                           parr[pinds[ii]+1:pinds[ii+1]+1],
                           **kwargs)
            lines.append(line[0])
        return lines

    def addScalebar(self, ax, borderpad=-1.8, sep=2):
        from neat.tools.plottools import scalebars
        scalebars.addScalebar(ax, hidex=False, hidey=False, matchy=False,
                                    labelx='$\mu$m',
                                    loc=8, borderpad=borderpad, sep=sep)
        ax.set_xticklabels([])

    def colorXAxis(self, ax, cmap, addScalebar=1, borderpad=-1.8):
        '''
        Color the x-axis of a plot according to the morphology.

        !!! Has to be called after all lines are plotted !!!

        Parameters
        ----------
            ax: :class:`matplotlib.axes.Axes` instance
                the ax object of which the x-axis will be colored
            cmap: :class:`matplotlib.colors.Colormap` instance
                Colormap that determines the color of each branch
            sizex: float
                Size of scalebar (in micron). If set to None, no scalebar is
                plotted.
            borderpad: float
                Borderpad of scalebar
        '''
        locs = self.locs['xaxis']
        # list of colors for plotting
        cs = {node.index: node.content['color'] for node in self}
        cplot = [cs[loc['node']] for loc in locs]
        max_cs = max(cplot)
        min_cs = min(cplot)
        if np.abs(max_cs - min_cs) < 1e-12:
            norm_cs = max_cs + 1e-2
        else:
            norm_cs = (max_cs - min_cs) * (1. + 1./100.)
        # necessary distance arrays
        pinds = self.getLeafLocinds('xaxis')
        assert len(pinds) > 0
        d2s = self.distancesToSoma('xaxis')
        # plot colored xaxis
        ylim = np.array(ax.get_ylim())
        ax.plot(self.xaxis[0:pinds[0]+1], [ylim[0]+1e-9 for _ in d2s[0:pinds[0]+1]],
                                    c=cmap((cplot[0]-min_cs)/norm_cs), lw=10)
        for ii in range(0,len(pinds)-1):
            if locs[pinds[ii]+1]['node'] in cs.keys():
                ax.plot(self.xaxis[pinds[ii]+1:pinds[ii+1]+1],
                        [ylim[0]+1e-9 for _ in d2s[pinds[ii]+1:pinds[ii+1]+1]],
                        c=cmap((cs[locs[pinds[ii]+1]['node']]-min_cs)/norm_cs), lw=10)
            else:
                ax.plot(self.xaxis[pinds[ii]+1:pinds[ii+1]+1],
                        [ylim[0]+1e-9 for _ in d2s[pinds[ii]+1:pinds[ii+1]+1]],
                        c='k', lw=10)
        ax.set_ylim((ylim[0], ylim[1]))
        # add scalebar
        if addScalebar:
            self.addScalebar(ax, borderpad=borderpad)
        ax.axes.get_xaxis().set_visible(False)

    def plot2DMorphology(self, ax, node_arg=None, cs=None, cmap=None,
                            use_radius=1, draw_soma_circle=1,
                            plotargs={}, textargs={},
                            marklocs=[], locargs={},
                            marklabels={}, labelargs={},
                            cb_draw=0, cb_orientation='vertical', cb_label='',
                            sb_draw=1, sb_scale=100, sb_width=5.):
        '''
        Plot the morphology projected on the x,y-plane

        Parameters
        ----------
            ax: :class:`matplotlib.axes.Axes` instance
                the ax object on which the plot will be drawn
            node_arg:
                see documentation of :func:`MorphTree._convertNodeArgToNodes`
            cs: dict {int: float}
                node indices are keys and the float value will correspond to the
                plotted color
            cmap: :class:`matplotlib.colors.Colormap` instance
            use_radius: bool
                If ``True``, uses the swc radius for the width of the line
                segments
            draw_soma_circle: bool
                If ``True``, draws the soma as a circle, otherwise doesn't draw
                soma
            plotargs: dict
                `kwargs` for :func:`matplotlib.pyplot.plot`. 'c'- or 'color'-
                argument will be overwritten when cs is defined. 'lw'- or
                'linewidth' argument will be multiplied with the swc radius of
                the node if `use_radius` is ``True``.
            textargs: dict
                text properties for various labels in the plot
            marklocs: list of tuples, dicts or instances of :class:`MorphLoc`
                Location that will be plotted on the morphology
            locargs: dict or list of dict
                `kwargs` for :func:`matplotlib.pyplot.plot` for the location.
                Use only point markers and no lines! When it is a single dict
                all location will have the same marker. When it is a list it
                should have the same length as `marklocs`.
            marklabels: dict {int: string}
                Keys are indices of locations in `marklocs`, values are strings
                that are used to annotate the corresponding locations
            labelargs: dict
                text properties for the location annotation
            cb_draw: bool
                Whether or not to draw a :class:`matplotlib.pyplot.colorbar()`
                instance.
            cb_orientation: string, 'vertical' or 'horizontal'
                The colorbars' orientation
            cb_label: string
                The label of the colorbar
            sb_draw: bool
                Whether or not to draw a scale bar
            sb_scale: float
                Lenght of the scale bar (micron)
            sb_width: float
                Width of the scale bar
        '''
        # default cmap
        if cmap == None:
            cmap = cm.get_cmap('jet')
        # ensure color is indicated by the 'c'-parameter in `plotargs`
        if 'color' in plotargs:
            plotargs['c'] = plotargs['color']
            del plotargs['color']
        elif 'c' not in plotargs:
            plotargs['c'] = 'k'
        # define a norm for the colors, if defined
        if cs != None:
            max_cs = cs[max(cs, key=cs.__getitem__)] # works for dict and list
            min_cs = cs[min(cs, key=cs.__getitem__)] # works for dict and list
            norm = pl.Normalize(vmin=min_cs, vmax=max_cs)
        # ensure linewidth is indicated as 'lw' in plotargs
        if 'linewidth' in plotargs:
            plotargs['lw'] = plotargs['linewidth']
            del plotargs['linewidth']
        elif 'lw' not in plotargs:
            plotargs['lw'] = 1.
        plotargs_orig = copy.deepcopy(plotargs)
        # locargs can be dictionary, so that the same properties hold for every
        # markloc, or can be list with the same size as marklocs, so that every
        # marker has different properties. `zorder` of the markers is also set
        # very high so that they are always in the foreground
        self.storeLocs(marklocs, 'plotlocs')
        xs = self.xs['plotlocs']
        if type(locargs) == dict:
            locargs['zorder'] = 1e4
            locargs = [locargs for _ in marklocs]
        else:
            assert len(locargs) == len(marklocs)
            for locarg in locargs:
                locarg['zorder'] = 1e4
        # `marklabels` is a dictionary with as keys the index of the loc in
        # `marklocs` to which the label belongs. `labelargs` is the same for
        # every label
        for ind in marklabels: assert ind < len(marklocs)
        # plot the tree
        xlim = [0.,0.]; ylim = [0.,0.]
        for node in self._convertNodeArgToNodes(node_arg):
            if node.xyz[0] < xlim[0]: xlim[0] = node.xyz[0]
            if node.xyz[0] > xlim[1]: xlim[1] = node.xyz[0]
            if node.xyz[1] < ylim[0]: ylim[0] = node.xyz[1]
            if node.xyz[1] > ylim[1]: ylim[1] = node.xyz[1]
            # find the locations that are on the current node
            inds = self.getLocindsOnNode('plotlocs', node)
            if node.parent_node is None:
                # node is soma, draw as circle if necessary
                if draw_soma_circle:
                    if cs is None:
                        pcolor = plotargs['c']
                    else:
                        plotargs['c'] = cmap(norm(cs[node.index]))
                    circ = patches.Circle(node.xyz[0:2], node.R,
                                          color=plotargs['c'])
                    ax.add_patch(circ)
                for ind in inds:
                    self._plotLoc(ax, ind, node.xyz[0], node.xyz[1],
                                   locargs, marklabels, labelargs)
            else:
                # plot line segment associated with node
                nxyz = node.xyz; pxyz = node.parent_node.xyz
                if cs is not None:
                    plotargs['c'] = cmap(norm(cs[node.index]))
                if use_radius:
                    plotargs['lw'] = plotargs_orig['lw'] * node.R
                ax.plot([pxyz[0], nxyz[0]], [pxyz[1], nxyz[1]], **plotargs)
                # plot the locations
                for ind in inds:
                    locxyz = pxyz + (nxyz - pxyz) * xs[ind]
                    self._plotLoc(ax, ind, locxyz[0], locxyz[1],
                                   locargs, marklabels, labelargs)
        # margins
        dx = xlim[1]-xlim[0]
        dy = ylim[1]-ylim[0]
        xlim[0] -= dx*.1; xlim[1] += dx*.1
        ylim[0] -= dy*.1; ylim[1] += dy*.1
        # draw a scale bar
        if sb_draw:
            scale = sb_scale
            dy = ylim[1]-ylim[0]
            dx = xlim[1]-xlim[0]
            ax.plot([xlim[0]+dx*0.01,xlim[0]+dx*0.01+scale],
                    [ylim[0]+dy*0.01,ylim[0]+dy*0.01],
                    'k', linewidth=sb_width)
            txt = ax.annotate(r'' + str(scale) + ' $\mu$m',
                              xy=(xlim[0]+dx*0.01+scale/2., ylim[0]+dy*0.02),
                              xycoords='data', xytext=(-28,8),
                              textcoords='offset points', **textargs)
            txt.set_path_effects([patheffects.withStroke(foreground="w",
                                                         linewidth=2)])
        ax.set_xlim(xlim); ax.set_ylim(ylim)
        ax.set_aspect('equal', 'datalim')
        if cs != None and cb_draw:
            # create colorbar ax
            divider = make_axes_locatable(ax)
            if cb_orientation == 'horizontal':
                cax = divider.append_axes("bottom", "5%", pad="3%")
            else:
                cax = divider.append_axes("right", "5%", pad="3%")
            # create a mappable
            sm = cm.ScalarMappable(cmap=cmap, norm=norm)
            sm._A = [] # fake array for scalar mappable
            # create the colorbar
            cb = pl.colorbar(sm, cax=cax, orientation=cb_orientation)
            ticks_cb = np.round(np.linspace(min_cs, max_cs, 7), decimals=1)
            cb.set_ticks(ticks_cb)
            if cb_orientation == 'horizontal':
                cb.ax.xaxis.set_ticks_position('bottom')
            else:
                cb.ax.yaxis.set_ticks_position('right')
            cb.set_label(cb_label, **textargs)
        ax.axes.get_xaxis().set_visible(0)
        ax.axes.get_yaxis().set_visible(0)
        ax.axison = 0

    def _plotLoc(self, ax, ind, xval, yval, locargs, marklabels, labelargs):
        '''
        plot a location on the morphology together with its annotation
        '''
        ax.plot(xval, yval, **locargs[ind])
        if ind in marklabels:
            txt = ax.annotate(marklabels[ind], xy=(xval, yval),
                              xycoords='data', xytext=(5,5),
                              textcoords='offset points', **labelargs)
            txt.set_path_effects([patheffects.withStroke(foreground="w",
                                                         linewidth=2)])

    def plotMorphologyInteractive(self, node_arg=None,
                            use_radius=1, draw_soma_circle=1,
                            plotargs={'c': 'k', 'lw': 1.},
                            project3d=False):
        '''
        Show the morphology either in 3d or projected on the x,y-plane. When
        a line segment is clicked, the associated node is printed.

        Parameters
        ----------
            ax: :class:`matplotlib.axes.Axes` instance
                the ax object on which the plot will be drawn
            node_arg:
                see documentation of :func:`MorphTree._convertNodeArgToNodes`
            use_radius: bool
                If ``True``, uses the swc radius for the width of the line
                segments
            draw_soma_circle: bool
                If ``True``, draws the soma as a circle, otherwise doesn't draw
                soma
        '''
        fig = pl.figure('Morphology interactive')
        ax = pl.gca(projection='3d') if project3d else pl.gca()
        # ax = pl.gca()
        if 'c' not in plotargs:
            plotargs.update({'c': 'k'})
        if 'linewidth' in plotargs:
            plotargs['lw'] = plotargs['linewidth']
            del plotargs['linewidth']
        if 'lw' not in plotargs:
            plotargs.update({'lw': 'k'})
        plotargs_orig = copy.deepcopy(plotargs)
        # plot the tree
        node_line_associators = {}
        for ii, node in enumerate(self._convertNodeArgToNodes(node_arg)):
            if node.parent_node is not None:
                # plot line segment associated with node
                nxyz = node.xyz; pxyz = node.parent_node.xyz
                if use_radius:
                    plotargs['lw'] = plotargs_orig['lw'] * node.R
                if project3d:
                    line = ax.plot([pxyz[0], nxyz[0]],
                                   [pxyz[1], nxyz[1]],
                                   [pxyz[2], nxyz[2]],
                                   label=str(ii), picker=2., **plotargs)
                else:
                    line = ax.plot([pxyz[0], nxyz[0]],
                                   [pxyz[1], nxyz[1]],
                                   label=str(ii), picker=2., **plotargs)
                node_line_associators.update({str(ii): node})
        ax.axes.get_xaxis().set_visible(0)
        ax.axes.get_yaxis().set_visible(0)
        ax.axison = 0

        # define the clickevent action
        def onPick(event):
            line = event.artist
            node = node_line_associators[line.get_label()]
            # print the associated node
            print '\n>>> line segment at ' + str(node) + \
                   ', distance to soma (um) = ' + \
                   str(self.pathLength({'node': node.index, 'x': 1},
                                       {'node': 1, 'x':0.}))
        # show morphology
        cid = fig.canvas.mpl_connect('pick_event', onPick)
        pl.show()

    @originalTreetypeDecorator
    def createNewTree(self, name):
        '''
        Creates a new tree where the locs of a given 'name' are now the nodes.

        Parameters
        ----------
            name: string
                the name under which the locations are stored that should be
                used to create the new tree

        Returns
        -------
            :class:`MorphTree`
                The new tree.
        '''
        self._tryName(name)
        # create new tree
        new_tree = MorphTree()
        # start the recursion
        ninds = self.getLocindsOnNode(name, self[1])
        # make soma node
        snode = self[1]
        p3d = (snode.xyz, snode.R, snode.swc_type)
        new_snode = self.createCorrespondingNode(1, p3d)
        new_snode.L = snode.L
        new_tree.setRoot(new_snode)
        new_nodes = [new_snode]
        # make two other soma nodes
        for cnode in snode.getChildNodes(skipinds=[]):
            if cnode.index in [2,3]:
                p3d = (cnode.xyz, cnode.R, cnode.swc_type)
                new_cnode = self.createCorrespondingNode(cnode.index, p3d)
                new_tree.addNodeWithParent(new_cnode, new_snode)
                new_nodes.append(new_cnode)
        # make rest of tree
        for cnode in snode.child_nodes:
            self._addNodesToTree(cnode, new_snode, new_tree, new_nodes, name)
        # set the lengths of the nodes
        for new_node in new_tree:
            if new_node.parent_node != None:
                L = np.sqrt(np.sum((new_node.parent_node.xyz - new_node.xyz)**2))
            else:
                L = 0.
            new_node.setLength(L)

        return new_tree

    def _addNodesToTree(self, node, new_pnode, new_tree, new_nodes, name):
        # get the specified locs
        xs = self.xs[name]
        # check which locinds are on the branch
        ninds = self.getLocindsOnNode(name, node)
        for ind in ninds:
            index = len(new_nodes) + 1
            # new coordinates
            new_xyz = node.parent_node.xyz * (1.-xs[ind]) + node.xyz * xs[ind]
            if node.parent_node.index == 1:
                new_radius = node.R
            else:
                new_radius = node.parent_node.R * (1.-xs[ind]) + node.R * xs[ind]
            # make new node
            p3d = (new_xyz, new_radius, node.swc_type)
            new_node = self.createCorrespondingNode(index, p3d)
            # add new node
            new_tree.addNodeWithParent(new_node, new_pnode)
            new_nodes.append(new_node)
        # continue with the children
        for cnode in node.child_nodes:
            self._addNodesToTree(cnode, new_node, new_tree, new_nodes, name)