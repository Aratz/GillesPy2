import os
import gillespy2
import numpy


def convert(filename, model_name=None, gillespy_model=None):
    try:
        import libsbml
    except ImportError:
        raise ImportError('libsbml is required to convert SBML files for GillesPy.')

    document = libsbml.readSBML(filename)
    errors = []
    error_count = document.getNumErrors()
    if error_count > 0:
        for i in range(error_count):
            error = document.getError(i)
            converter_code = 0
            converter_code = -10

            errors.append(["SBML {0}, code {1}, line {2}: {3}".format(error.getSeverityAsString(), error.getErrorId(),
                                                                      error.getLine(), error.getMessage()),
                           converter_code])
    if min([code for error, code in errors] + [0]) < 0:
        return None, errors
    model = document.getModel()
    if model_name is None:
        model_name = model.getName()
    if gillespy_model is None:
        gillespy_model = gillespy2.Model(name=model_name)
    gillespy_model.units = "concentration"
    for i in range(model.getNumSpecies()):
        species = model.getSpecies(i)
        if species.getId() == 'EmptySet':
            errors.append([
                              "EmptySet species detected in model on line {0}. EmptySet is not an explicit species in "
                              "gillespy".format(
                                  species.getLine()), 0])
            continue
        name = species.getId()
        if species.isSetInitialAmount():
            value = species.getInitialAmount()
        elif species.isSetInitialConcentration():
            value = species.getInitialConcentration()
        else:
            rule = model.getRule(species.getId())
            if rule:
                msg = ""
                if rule.isAssignment():
                    msg = "assignment "
                elif rule.isRate():
                    msg = "rate "
                elif rule.isAlgebraic():
                    msg = "algebraic "

                msg += "rule"

                errors.append([
                                  "Species '{0}' does not have any initial conditions. Associated {1} '{2}' found, "
                                  "but {1}s are not supported in gillespy. Assuming initial condition 0".format(
                                      species.getId(), msg, rule.getId()), 0])
            else:
                errors.append([
                                  "Species '{0}' does not have any initial conditions or rules. Assuming initial "
                                  "condition 0".format(
                                      species.getId()), 0])

            value = 0

        if value < 0.0:
            errors.append([
                              "Species '{0}' has negative initial condition ({1}). gillespy does not support negative "
                              "initial conditions. Assuming initial condition 0".format(
                                  species.getId(), value), -5])
            value = 0

        gillespy_species = gillespy2.Species(name=name, initial_value=value)
        gillespy_model.add_species([gillespy_species])

    for i in range(model.getNumParameters()):
        parameter = model.getParameter(i)
        name = parameter.getId()
        value = parameter.getValue()
        is_species = False
        rule = None

        for i in range(model.getNumRules()):
            rule = model.getRule(i)
            rule_name = rule.getId()
            if name == rule_name:
                is_species = True
                break

        if is_species:
            gillespy_species = gillespy2.Species(name=name, initial_value=value, continuous=True)
            gillespy_model.add_species([gillespy_species])
            '''
            gillespy_rate_rule = gillespy2.RateRule(gillespy_model.listOfSpecies[name], 
                    libsbml.formulaToString(rule.getMath()))
            gillespy_model.add_rate_rule([gillespy_rate_rule])
            #   print(gillespy_rate_rule)
            '''
        else:
            gillespy_parameter = gillespy2.Parameter(name=name, expression=value)
            gillespy_model.add_parameter([gillespy_parameter])

    for i in range(model.getNumCompartments()):
        compartment = model.getCompartment(i)
        name = compartment.getId()
        value = compartment.getSize()

        gillespy_parameter = gillespy2.Parameter(name=name, expression=value)
        gillespy_model.add_parameter([gillespy_parameter])

    # local parameters
    for i in range(model.getNumReactions()):
        reaction = model.getReaction(i)
        kinetic_law = reaction.getKineticLaw()

        for j in range(kinetic_law.getNumParameters()):
            parameter = kinetic_law.getParameter(j)
            name = parameter.getId()
            value = parameter.getValue()
            gillespy_parameter = gillespy2.Parameter(name=name, expression=value)
            gillespy_model.add_parameter([gillespy_parameter])

    # reactions
    for i in range(model.getNumReactions()):
        reaction = model.getReaction(i)
        name = reaction.getId()

        reactants = {}
        products = {}

        for j in range(reaction.getNumReactants()):
            species = reaction.getReactant(j)

            if species.getSpecies() == "EmptySet":
                errors.append([
                                  "EmptySet species detected as reactant in reaction '{0}' on line {1}. EmptySet is "
                                  "not an explicit species in gillespy".format(
                                      reaction.getId(), species.getLine()), 0])
            else:
                reactants[species.getSpecies()] = species.getStoichiometry()

        # get products
        for j in range(reaction.getNumProducts()):
            species = reaction.getProduct(j)

            if species.getSpecies() == "EmptySet":
                errors.append([
                                  "EmptySet species detected as product in reaction '{0}' on line {1}. EmptySet is "
                                  "not an explicit species in gillespy".format(
                                      reaction.getId(), species.getLine()), 0])
            else:
                products[species.getSpecies()] = species.getStoichiometry()

        # propensity
        kinetic_law = reaction.getKineticLaw()
        propensity = kinetic_law.getFormula()

        gillespy_reaction = gillespy2.Reaction(name=name, reactants=reactants, products=products,
                                             propensity_function=propensity)

        gillespy_model.add_reaction([gillespy_reaction])

    for i in range(model.getNumRules()):
        rule = model.getRule(i)
        #   print(rule.getId())

        t = []

        if rule.isCompartmentVolume():
            t.append('compartment')
        if rule.isParameter():
            t.append('parameter')
        elif rule.isAssignment():
            t.append('assignment')
        elif rule.isRate():
            t.append('rate')
        elif rule.isAlgebraic():
            t.append('algebraic')

        if len(t) > 0:
            t[0] = t[0].capitalize()

            msg = ", ".join(t)
            msg += " rule"
        else:
            msg = "Rule"

        gillespy_rate_rule = gillespy2.RateRule(rule.getId(), 
                    libsbml.formulaToString(rule.getMath()))
        gillespy_model.add_rate_rule([gillespy_rate_rule])

    for i in range(model.getNumCompartments()):
        compartment = model.getCompartment(i)

        errors.append([
                          "Compartment '{0}' found on line '{1}' with volume '{2}' and dimension '{3}'. gillespy "
                          "assumes a single well-mixed, reaction volume".format(
                              compartment.getId(), compartment.getLine(), compartment.getVolume(),
                              compartment.getSpatialDimensions()), -5])

    for i in range(model.getNumConstraints()):
        constraint = model.getConstraint(i)

        errors.append([
                          "Constraint '{0}' found on line '{1}' with equation '{2}'. gillespy does not support SBML "
                          "Constraints".format(
                              constraint.getId(), constraint.getLine(), libsbml.formulaToString(constraint.getMath())),
                          -5])

    for i in range(model.getNumEvents()):
        event = model.getEvent(i)

        errors.append([
                          "Event '{0}' found on line '{1}' with trigger equation '{2}'. gillespy does not support "
                          "SBML Events".format(
                              event.getId(), event.getLine(), libsbml.formulaToString(event.getTrigger().getMath())),
                          -5])

    for i in range(model.getNumFunctionDefinitions()):
        function = model.getFunctionDefinition(i)

        errors.append([
                          "Function '{0}' found on line '{1}' with equation '{2}'. gillespy does not support SBML "
                          "Function Definitions".format(
                              function.getId(), function.getLine(), libsbml.formulaToString(function.getMath())), -5])
    return gillespy_model, errors



