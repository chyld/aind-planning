from aimacode.logic import PropKB
from aimacode.planning import Action
from aimacode.search import (
    Node, Problem,
)
from aimacode.utils import expr
from lp_utils import (
    FluentState, encode_state, decode_state,
)
from my_planning_graph import PlanningGraph

from functools import lru_cache


class AirCargoProblem(Problem):
    def __init__(self, cargos, planes, airports, initial: FluentState, goal: list):
        """

        :param cargos: list of str
            cargos in the problem
        :param planes: list of str
            planes in the problem
        :param airports: list of str
            airports in the problem
        :param initial: FluentState object
            positive and negative literal fluents (as expr) describing initial state
        :param goal: list of expr
            literal fluents required for goal test
        """
        self.state_map = initial.pos + initial.neg
        self.initial_state_TF = encode_state(initial, self.state_map)
        Problem.__init__(self, self.initial_state_TF, goal=goal)
        self.cargos = cargos
        self.planes = planes
        self.airports = airports
        self.actions_list = self.get_actions()

    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #

    def get_actions(self):
        """
        This method creates concrete actions (no variables) for all actions in the problem
        domain action schema and turns them into complete Action objects as defined in the
        aimacode.planning module. It is computationally expensive to call this method directly;
        however, it is called in the constructor and the results cached in the `actions_list` property.

        Returns:
        ----------
        list<Action>
            list of Action objects
        """

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ #
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ #

        def load_actions():
            """Create all concrete Load actions and return a list

            Action(Load(c, p, a),
                PRECOND: At(c, a) ∧ At(p, a) ∧ Cargo(c) ∧ Plane(p) ∧ Airport(a)
                EFFECT: ¬ At(c, a) ∧ In(c, p))

            :return: list of Action objects
            """
            loads = []
            for c in self.cargos:
                for p in self.planes:
                    for a in self.airports:
                            precond_pos = [expr("At({}, {})".format(c, a)), expr("At({}, {})".format(p, a))]
                            precond_neg = []
                            effect_add = [expr("In({}, {})".format(c, p))]
                            effect_rem = [expr("At({}, {})".format(c, a))]
                            load = Action(expr("Load({}, {}, {})".format(c, p, a)),
                                         [precond_pos, precond_neg],
                                         [effect_add, effect_rem])
                            loads.append(load)
            return loads

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ #
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ #

        def unload_actions():
            """Create all concrete Unload actions and return a list

            Action(Unload(c, p, a),
                PRECOND: In(c, p) ∧ At(p, a) ∧ Cargo(c) ∧ Plane(p) ∧ Airport(a)
                EFFECT: At(c, a) ∧ ¬ In(c, p))

            :return: list of Action objects
            """
            unloads = []
            for c in self.cargos:
                for p in self.planes:
                    for a in self.airports:
                            precond_pos = [expr("In({}, {})".format(c, p)), expr("At({}, {})".format(p, a))]
                            precond_neg = []
                            effect_add = [expr("At({}, {})".format(c, a))]
                            effect_rem = [expr("In({}, {})".format(c, p))]
                            unload = Action(expr("Unload({}, {}, {})".format(c, p, a)),
                                         [precond_pos, precond_neg],
                                         [effect_add, effect_rem])
                            unloads.append(unload)
            return unloads

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ #
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ #

        def fly_actions():
            """Create all concrete Fly actions and return a list

            Action(Fly(p, from, to),
                PRECOND: At(p, from) ∧ Plane(p) ∧ Airport(from) ∧ Airport(to)
                EFFECT: ¬ At(p, from) ∧ At(p, to))

            :return: list of Action objects
            """
            flys = []
            for fr in self.airports:
                for to in self.airports:
                    if fr != to:
                        for p in self.planes:
                            precond_pos = [expr("At({}, {})".format(p, fr))]
                            precond_neg = []
                            effect_add = [expr("At({}, {})".format(p, to))]
                            effect_rem = [expr("At({}, {})".format(p, fr))]
                            fly = Action(expr("Fly({}, {}, {})".format(p, fr, to)),
                                         [precond_pos, precond_neg],
                                         [effect_add, effect_rem])
                            flys.append(fly)
            return flys

        return load_actions() + unload_actions() + fly_actions()

    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #

    def actions(self, state: str) -> list:
        """ Return the actions that can be executed in the given state.

        :param state: str
            state represented as T/F string of mapped fluents (state variables)
            e.g. 'FTTTFF'
        :return: list of Action objects

        I take the current state, kb, and then for each action, I ask the action
        to check its precondition - based on the current state and the arguments
        to the action. If the precondition check passes, then the action is added
        to a list of possible actions that can be traversed from a node in the graph.
        """
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).sentence())
        return [a for a in self.actions_list if a.check_precond(kb, a.args)]        

    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #

    def result(self, state: str, action: Action):
        """ Return the state that results from executing the given
        action in the given state. The action must be one of
        self.actions(state).

        :param state: state entering node
        :param action: Action applied
        :return: resulting state after action

        I take an action, and call it, passing in the current state
        and its arguments. This causes kb.clauses to mutate from one
        state to the next. I then traverse the updated kb.clauses. If
        a clause has a "~" then I add it to the negative list, else I
        add it to the positive list. I then turn these two lists into
        an updated state and return.
        """
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).sentence())
        action(kb, action.args) 
        pos = []; neg = []
        for e in kb.clauses:
            neg.append(e) if e.op == '~' else pos.append(e)
        return encode_state(FluentState(pos, neg), self.state_map)

    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #

    def goal_test(self, state: str) -> bool:
        """ Test the state to see if goal is reached

        :param state: str representing state
        :return: bool
        """
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).pos_sentence())
        for clause in self.goal:
            if clause not in kb.clauses:
                return False
        return True

    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #

    def h_1(self, node: Node):
        h_const = 1
        return h_const

    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #

    @lru_cache(maxsize=8192)
    def h_pg_levelsum(self, node: Node):
        """This heuristic uses a planning graph representation of the problem
        state space to estimate the sum of all actions that must be carried
        out from the current state in order to satisfy each individual goal
        condition.
        """
        pg = PlanningGraph(self, node.state)
        pg_levelsum = pg.h_levelsum()
        return pg_levelsum

    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #

    @lru_cache(maxsize=8192)
    def h_ignore_preconditions(self, node: Node):
        """This heuristic estimates the minimum number of actions that must be
        carried out from the current state in order to satisfy all of the goal
        conditions by ignoring the preconditions required for an action to be
        executed.

        I count the number of uncompleted goals in the current state and return
        that value to the caller. For example, if a state has three incomplete
        goals, and if we assume one action will complete one goal, then
        the cost - or the number of actions - required to move from this state
        to the final state with all goals completed, is three.

        - From page 376 in AIMA 3rd -
        Every action becomes applicable in every state, and any single goal fluent
        can be achieved in one step (if there is an applicable action—if not, the problem
        is impossible). This almost implies that the number of steps required to solve
        the relaxed problem is the number of unsatisfied goals—almost but not
        quite, because (1) some action may achieve multiple goals and (2) some actions may undo
        the effects of others. For many problems an accurate heuristic is obtained by considering (1)
        and ignoring (2). First, we relax the actions by removing all preconditions and all effects
        except those that are literals in the goal. Then, we count the minimum number of actions
        required such that the union of those actions’ effects satisfies the goal.
        """
        kb = PropKB()
        kb.tell(decode_state(node.state, self.state_map).sentence())
        return len([g for g in self.goal if g not in kb.clauses])

    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #
    # --------------------------------------------------------------------------------- #

def air_cargo_p1() -> AirCargoProblem:
    cargos = ['C1', 'C2']
    planes = ['P1', 'P2']
    airports = ['JFK', 'SFO']
    pos = [
           expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
          ]
    neg = [
           expr('At(C2, SFO)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),
           expr('At(C1, JFK)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           expr('At(P1, JFK)'),
           expr('At(P2, SFO)'),
          ]
    init = FluentState(pos, neg)
    goal = [
            expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
           ]
    return AirCargoProblem(cargos, planes, airports, init, goal)

def air_cargo_p2() -> AirCargoProblem:
    cargos = ['C1', 'C2', 'C3']
    planes = ['P1', 'P2', 'P3']
    airports = ['JFK', 'SFO', 'ATL']
    pos = [
           expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(C3, ATL)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           expr('At(P3, ATL)'),
          ]
    neg = [
           expr('At(C1, JFK)'),
           expr('At(C1, ATL)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           expr('In(C1, P3)'),
           
           expr('At(C2, SFO)'),
           expr('At(C2, ATL)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),
           expr('In(C2, P3)'),
           
           expr('At(C3, SFO)'),
           expr('At(C3, JFK)'),
           expr('In(C3, P1)'),
           expr('In(C3, P2)'),
           expr('In(C3, P3)'),

           expr('At(P1, JFK)'),
           expr('At(P1, ATL)'),

           expr('At(P2, SFO)'),
           expr('At(P2, ATL)'),

           expr('At(P3, SFO)'),
           expr('At(P3, JFK)'),
          ]
    init = FluentState(pos, neg)
    goal = [
            expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            expr('At(C3, SFO)'),
           ]
    return AirCargoProblem(cargos, planes, airports, init, goal)

def air_cargo_p3() -> AirCargoProblem:
    cargos = ['C1', 'C2', 'C3', 'C4']
    planes = ['P1', 'P2']
    airports = ['JFK', 'SFO', 'ATL', 'ORD']
    pos = [
           expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(C3, ATL)'),
           expr('At(C4, ORD)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
          ]
    neg = [
           expr('At(C1, JFK)'),
           expr('At(C1, ATL)'),
           expr('At(C1, ORD)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           
           expr('At(C2, SFO)'),
           expr('At(C2, ATL)'),
           expr('At(C2, ORD)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),

           expr('At(C3, SFO)'),
           expr('At(C3, JFK)'),
           expr('At(C3, ORD)'),
           expr('In(C3, P1)'),
           expr('In(C3, P2)'),

           expr('At(C4, SFO)'),
           expr('At(C4, JFK)'),
           expr('At(C4, ATL)'),
           expr('In(C4, P1)'),
           expr('In(C4, P2)'),

           expr('At(P1, JFK)'),
           expr('At(P1, ATL)'),
           expr('At(P1, ORD)'),

           expr('At(P2, SFO)'),
           expr('At(P2, ATL)'),
           expr('At(P2, ORD)'),
          ]
    init = FluentState(pos, neg)
    goal = [
            expr('At(C1, JFK)'),
            expr('At(C3, JFK)'),
            expr('At(C2, SFO)'),
            expr('At(C4, SFO)'),
           ]
    return AirCargoProblem(cargos, planes, airports, init, goal)
