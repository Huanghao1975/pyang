"""Flattens provided YANG schema and outputs XPath attributes as CSV.
"""

import optparse
import csv

from pyang import plugin
from pyang import statements, types


def pyang_plugin_init():
    plugin.register_plugin(FlattenPlugin())


class FlattenPlugin(plugin.PyangPlugin):
    def __init__(self):
        plugin.PyangPlugin.__init__(self, "flatten")

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts["flatten"] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option(
                "--flatten-no-header",
                dest="flatten_no_header",
                action="store_true",
                help="Do not emit the CSV header.",
            ),
            optparse.make_option(
                "--flatten-type",
                dest="flatten_type",
                action="store_true",
                help="Output the top-level type.",
            ),
            optparse.make_option(
                "--flatten-primitive-type",
                dest="flatten_primitive_type",
                action="store_true",
                help="Output the primitive type.",
            ),
            optparse.make_option(
                "--flatten-permission",
                dest="flatten_permission",
                action="store_true",
                help="Output config property.",
            ),
            optparse.make_option(
                "--flatten-description",
                dest="flatten_description",
                action="store_true",
                help="Output the description.",
            ),
            optparse.make_option(
                "--flatten-filter-keyword",
                dest="flatten_filter_keyword",
                help="Filter output to only desired keywords.",
                action="append",
                choices=list(statements.data_keywords),
            ),
            optparse.make_option(
                "--flatten-filter-primitive",
                dest="flatten_filter_primitive",
                help="Filter output to only desired primitive types.",
                action="append",
                choices=list(types.yang_type_specs.keys()),
            ),
            optparse.make_option(
                "--flatten-filter-permission",
                dest="flatten_filter_permission",
                help="Filter output to ro or rw (config property).",
                choices=["ro", "rw"],
            ),
            optparse.make_option(
                "--flatten-csv-dialect",
                dest="flatten_csv_dialect",
                default="excel",
                help="CSV dialect for output.",
                choices=["excel", "excel-tab", "unix"],
            ),
        ]
        g = optparser.add_option_group("Flatten output specific options")
        g.add_options(optlist)

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False
        self.__field_names = ["xpath"]
        if ctx.opts.flatten_primitive_type:
            self.__field_names.append("primitive_type")
        if ctx.opts.flatten_permission:
            self.__field_names.append("permission")
        if ctx.opts.flatten_type:
            self.__field_names.append("type")
        if ctx.opts.flatten_description:
            self.__field_names.append("description")
        self.__field_names_set = set(self.__field_names)

    def emit(self, ctx, modules, fd):
        output_writer = csv.DictWriter(
            fd, fieldnames=self.__field_names, dialect=ctx.opts.flatten_csv_dialect
        )
        if not ctx.opts.flatten_no_header:
            output_writer.writeheader()
        for module in modules:
            self.output_module(ctx, module, output_writer)

    def output_module(self, ctx, module, output_writer):
        if not hasattr(module, "i_children"):
            return
        module_children = (
            child
            for child in module.i_children
            if child.keyword in statements.data_definition_keywords
        )
        for child in module_children:
            # Keys map to self.__field_names for CSV output
            output_content = {
                "xpath": statements.get_xpath(child, prefix_to_module=True)
            }
            primitive_type = statements.get_primitive_type(child)
            permission = "rw" if getattr(child, "i_config", False) else "ro"
            if ctx.opts.flatten_type:
                output_content["type"] = statements.get_qualified_type(child)
            if ctx.opts.flatten_primitive_type:
                output_content["primitive_type"] = statements.get_primitive_type(child)
            if ctx.opts.flatten_permission:
                output_content["permission"] = permission
            if ctx.opts.flatten_description:
                output_content["description"] = statements.get_description(child)
            if output_content.keys() != self.__field_names_set:
                raise Exception("Output keys do not match CSV field names!")
            # Filters are specified as a positive in the command line arguments
            # In this case we're negating compared to what we want to output
            output_filters = set(
                [
                    ctx.opts.flatten_filter_keyword
                    and child.keyword not in ctx.opts.flatten_filter_keyword,
                    ctx.opts.flatten_filter_primitive
                    and primitive_type not in ctx.opts.flatten_filter_primitive,
                    ctx.opts.flatten_filter_permission
                    and permission != ctx.opts.flatten_filter_permission,
                ]
            )
            if not any(output_filters):
                # We want to traverse the entire tree for output
                # Simply don't output what we don't want, don't stop processing
                output_writer.writerow(output_content)
            if hasattr(child, "i_children"):
                self.output_module(ctx, child, output_writer)
