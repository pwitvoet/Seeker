# Seeker - a pathfinding-based language
#
# "
# Some say it's the journey that counts.
# Fair enough.
# But without goal there is no journey.
# "
#
# Seeker programs consist of a bidirectional graph, where each node holds a
# value. Nodes can be connected to any number of other nodes. A Seeker program
# can connect and disconnect nodes, as well as create and destroy nodes at
# run-time.
#
# Each execution step, a Seeker thread processes the value of the node it's
# currently pointing to, and then moves forward to the next node. But how is
# 'forward' determined in a bidirectional graph? Simply by determining the
# shortest route between the current node and the thread's target node.
#
# When a program is loaded, the Seeker interpreter creates a thread that starts
# at the node with the lowest number, and it's destination is set to the node
# with the next-lowest number.
#
# The following opcodes are available:
#  1: set destination (node number)
#  2: change connection (node number, node number, 0 = disconnect-if-connected
#       / other = connect-if-not-connected)
#  3: change node (node number, 0 = destroy-if-exists
#       / other = create-if-not-exists)
#  4: increment node value (node number)
#  5: decrement node value (node number)
#  6: copy value from node to node (from node number, to node number)
#  7: output node value (node number)
# When Seeker is started in extended mode, the following opcodes become
# available:
#  8: create thread (start node number, destination node number)
#  9: breakpoint ()
#
import inspect, sys, optparse


class Node(object):
    def __init__(self, value):
        super(Node, self).__init__()
        
        self.value = value
        self.connections = []
    #
    
    def connect(self, node):
        if node not in self.connections:
            self.connections.append(node)
        if self not in node.connections:
            node.connections.append(self)
    #
    
    def disconnect(self, node):
        if node in self.connections:
            self.connections.remove(node)
        if self in node.connections:
            node.connections.remove(self)
    #
    
    def disconnectAll(self):
        for node in self.connections:
            if self in node.connections:
                node.connections.remove(self)
        self.connections = []
    #
#

class PathNode(object):
    def __init__(self, parent, node):
        super(PathNode, self).__init__()
        
        self.parent = parent
        self.node = node
        self.cost = 0 if parent is None else parent.cost + 1
    #
#

class Thread(object):
    def __init__(self, thread_id, start_node, destination_node):
        super(Thread, self).__init__()
        
        self.thread_id = thread_id
        self.current_node = start_node
        self.destination_node = destination_node
        
        self.stack = []
        self.stalled = False
    #
#

class Operation(object):
    def __init__(self, function, extended = False):
        super(Operation, self).__init__()
        
        self.arguments_count = len(inspect.getargspec(function).args) - (2 if inspect.ismethod(function) else 1)
        self.function = function
        self.extended = extended
    #
    
    @property
    def name(self):
        return self.function.__name__
    #
    
    def execute(self, thread, arguments):
        self.function(thread, *arguments)
    #
#

class SeekerInterpreter(object):
    def __init__(self):
        super(SeekerInterpreter, self).__init__()
        
        self.nodes = {}
        self.threads = []
        self.next_thread_id = 0
        self.paused = False
        self.output = ''
        
        self.verbose = False
        self.extended = False
        
        self.operations = {
            1: Operation(self.op_setDestination),
            2: Operation(self.op_setConnection),
            3: Operation(self.op_createDestroyNode),
            4: Operation(self.op_increment),
            5: Operation(self.op_decrement),
            6: Operation(self.op_copy),
            
            7: Operation(self.op_createThread, extended = True),
            8: Operation(self.op_breakpoint, extended = True),
        }
        
        # Node 0 is the special IO node - it can not be removed.
        self.io_node_id = 0
    #
    
    def reset(self):
        self.nodes = {}
        self.threads = []
        self.next_thread_id = 0
        self.paused = False
        self.output = ''
    #
    
    def loadString(self, seeker_string):
        self.reset()
        
        unresolved_connections = []
        
        node_id = None
        digits_buffer = ''
        operator = None
        for c in seeker_string + ' ':
            if c.isdigit():
                digits_buffer += c
            elif c in ':-':
                if digits_buffer != '':
                    operator = c
                    node_id = int(digits_buffer)
                    digits_buffer = ''
                else:
                    digits_buffer += c
            else:
                if None not in [node_id, operator] and digits_buffer != '':
                    if operator == ':':
                        self.nodes[node_id] = Node(int(digits_buffer))
                    elif operator == '-':
                        other_node_id = int(digits_buffer)
                        if node_id in self.nodes and other_node_id in self.nodes:
                            self.nodes[node_id].connect(self.nodes[other_node_id])
                        else:
                            unresolved_connections.append((node_id, other_node_id))
                    
                    node_id = None
                    digits_buffer = ''
                    operator = None
                    
        
        for node_id, other_node_id in unresolved_connections:
            if node_id in self.nodes and other_node_id in self.nodes:
                self.nodes[node_id].connect(self.nodes[other_node_id])
            else:
                # TODO: Also make a warning / error callback? :)
                print('Warning: failed to connect nodes {0} and {1}'.format(node_id, other_node_id))
        
        # A program requires node 0 and node 1 to exist in order to run:
        if 0 in self.nodes and 1 in self.nodes:
            start_node, destination_node = self.nodes[0], self.nodes[1]
            self.threads.append(Thread(self.nextThreadId(), start_node, destination_node))
    #
    
    def loadFile(self, seeker_filename):
        with open(seeker_filename) as f:
            self.loadString(f.read())
    #
    
    def run(self):
        self.paused = False
        while self.execute_step():
            pass
        
        if self.paused:
            if self.verbose:
                print('Program paused')
        else:
            if self.verbose:
                print('Program terminated, no active threads left.')
    #
    
    def execute_step(self):
        if self.paused or not self.hasRunningThreads():
            return False
        
        # Only start executing new threads during the next execution step:
        threads = self.threads[:]
        for thread in threads:
            if not thread.stalled:
                thread.stack.append(thread.current_node.value)
                
                # Does the stack start with a valid opcode?
                opcode = thread.stack[0]
                if opcode in self.operations and (not self.operations[opcode].extended or self.extended):
                    operation = self.operations[opcode]
                    arguments = thread.stack[1:]
                    
                    # Are there enough arguments on the stack to execute the opcode?
                    if len(arguments) == operation.arguments_count:
                        if self.verbose:
                            print('Thread {0} executing {1}({2}).'.format(thread.thread_id, operation.name, ' '.join(str(argument) for argument in arguments)))
                        
                        operation.execute(thread, arguments)
                        thread.stack = []
                else:
                    # Stack does not start with a valid opcode, so ignore it:
                    thread.stack = []
            
            # End of the line for this thread? Then terminate, because there's no way
            # we can get this thread moving again:
            if thread.current_node == thread.destination_node:
                if self.verbose:
                    print('Thread {0} is terminated.'.format(thread.thread_id))
                
                self.threads.remove(thread)
            else:
                route = self.findRoute(thread.current_node, thread.destination_node)
                if route is None:
                    # No route to destination, so stall this thread:
                    if self.verbose:
                        print('Thread {0} is stalled.'.format(thread.thread_id))
                    
                    thread.stalled = True
                else:
                    # Move to the next node. We could cache the route but then we need
                    # to take care of invalidating route caches when the graph changes.
                    # So there's room for some optimization:
                    if self.verbose:
                        node_id = [number for number, node in filter(lambda item: item[1] == route[0], self.nodes.items())][0]
                        print('Thread {0} is moving to node {1}.'.format(thread.thread_id, node_id))
                    
                    thread.stalled = False
                    thread.current_node = route[0]
        
        return self.hasRunningThreads() and not self.paused
    #
    
    def hasRunningThreads(self):
        return any(not thread.stalled for thread in self.threads)
    #
    
    def nextThreadId(self):
        self.next_thread_id += 1
        return self.next_thread_id - 1
    #
    
    def findRoute(self, start_node, destination_node):
        if start_node == destination_node:
            # Already there, no need to move:
            return []
        elif start_node is None or destination_node is None:
            # Can't find a route to or from a non-existing node
            return None
        
        options = {start_node: PathNode(None, start_node)}
        visited = {}
        
        while len(options) > 0:
            node, path_node = sorted(options.items(), key = lambda item: item[1].cost)[0]
            visited[node] = options.pop(node)
            
            for connected_node in node.connections:
                if connected_node not in options and connected_node not in visited:
                    options[connected_node] = PathNode(path_node, connected_node)
                    
                    if connected_node == destination_node:
                        # Route found, create a list of nodes that form the path:
                        path = []
                        path_node = options[connected_node]
                        while path_node.parent is not None:
                            path.append(path_node.node)
                            path_node = path_node.parent
                        return [node for node in reversed(path)]
        
        # Couldn't find a route:
        return None
    #
    
    def get_input(self):
        if len(self.input) > 0:
            value = self.input[0]
            self.input = self.input[1:]
            return value
        else:
            return -1
    #
    
    def write_output(self, value):
        self.output += chr(value % 256)
        print(self.output[-1])
    #
    
    def op_setDestination(self, thread, node_id):
        if node_id in self.nodes:
            thread.destination_node = self.nodes[node_id]
    #
    
    def op_setConnection(self, thread, node_id, other_node_id, connect):
        if node_id in self.nodes and other_node_id in self.nodes:
            if connect <= 0:
                self.nodes[node_id].disconnect(self.nodes[other_node_id])
            else:
                self.nodes[node_id].connect(self.nodes[other_node_id])
    #
    
    def op_createDestroyNode(self, thread, node_id, create):
        if create <= 0 and node_id in self.nodes:
            node = self.nodes.pop(node_id)
            node.disconnectAll()
        elif create > 0 and node_id not in self.nodes:
            self.nodes[node_id] = Node(0)
    #
    
    def op_increment(self, thread, node_id):
        if node_id in self.nodes:
            self.nodes[node_id].value += 1
    #
    
    def op_decrement(self, thread, node_id):
        if node_id in self.nodes:
            self.nodes[node_id].value -= 1
    #
    
    def op_copy(self, thread, from_node_id, to_node_id):
        if from_node_id in self.nodes and to_node_id in self.nodes:
            # The IO node is special: copying from it reads an input byte,
            # copying to it writes to output. It's possible to move an input
            # byte directly to the output with one copy operation.
            
            value = 0
            if from_node_id == self.io_node_id:
                value = self.get_input()
            else:
                value = self.nodes[from_node_id].value
            
            if to_node_id == self.io_node_id:
                self.write_output(value)
            else:
                self.nodes[to_node_id].value = value
    #
    
    def op_createThread(self, thread, start_node_id, destination_node_id):
        if start_node_id in self.nodes and destination_node_id in self.nodes:
            self.threads.append(Thread(self.nextThreadId(), self.nodes[start_node_id], self.nodes[destination_node_id]))
    #
    
    def op_breakpoint(self, thread):
        self.paused = True
    #
#

interpreter = None
if __name__ == '__main__':
    parser = optparse.OptionParser(usage = 'usage: %prog [options] skr-file-path')
    parser.add_option('-i', '--input',
                        help = 'Input file path.')
    parser.add_option('-o', '--output',
                        help = 'Output file path. Leave empty to use standard output.')
    parser.add_option('-v', '--verbose',
                        default = False,
                        action = 'store_true',
                        help = 'Enables verbose mode, useful for debugging.')
    parser.add_option('-x', '--extended',
                        default = False,
                        action = 'store_true',
                        help = 'Enables extended mode, which unlocks additional opcodes. Useful for more advances programs.')
    
    (options, args) = parser.parse_args()
    
    if len(args) < 1:
        parser.print_help()
    else:
        interpreter = SeekerInterpreter()
        interpreter.verbose = options.verbose
        interpreter.extended = options.extended
        interpreter.loadFile(args[0])
        interpreter.run()
#