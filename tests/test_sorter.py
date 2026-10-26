import textwrap
import unittest

from terraforder import ParseError, sort_source


def tf(source: str) -> str:
    return textwrap.dedent(source).lstrip("\n")


def sort(source: str, **kwargs) -> str:
    return sort_source(tf(source), **kwargs)[0]


class SortTests(unittest.TestCase):
    def test_groups_by_type_then_sorts_labels(self):
        source = """
            output "b" {
              value = 1
            }
            resource "aws_s3_bucket" "logs" {
              bucket = "logs"
            }
            variable "zone" {}
            resource "aws_instance" "web" {
              ami = "x"
            }
            variable "region" {}
            terraform {
              required_version = ">= 1.0"
            }
            provider "aws" {
              region = var.region
            }
            data "aws_ami" "ubuntu" {}
            locals {
              name = "x"
            }
            module "vpc" {
              source = "./vpc"
            }
            output "a" {
              value = 2
            }
        """
        _, items = sort_source(tf(source))
        self.assertEqual(
            [item.address for item in items],
            [
                "terraform",
                "provider.aws",
                "variable.region",
                "variable.zone",
                "locals",
                "data.aws_ami.ubuntu",
                "resource.aws_instance.web",
                "resource.aws_s3_bucket.logs",
                "module.vpc",
                "output.a",
                "output.b",
            ],
        )

    def test_output_is_separated_by_single_blank_lines(self):
        source = """
            variable "b" {}


            variable "a" {
              default = 1
            }
        """
        self.assertEqual(
            sort(source),
            tf("""
                variable "a" {
                  default = 1
                }

                variable "b" {}
            """),
        )

    def test_sorted_output_is_stable(self):
        source = """
            resource "x" "b" {}
            resource "x" "a" {}
            variable "c" {}
        """
        once = sort(source)
        self.assertEqual(sort_source(once)[0], once)

    def test_case_insensitive_order(self):
        _, items = sort_source(tf("""
            variable "beta" {}
            variable "Alpha" {}
        """))
        self.assertEqual([i.labels for i in items], [("Alpha",), ("beta",)])

    def test_unknown_block_types_go_last_alphabetically(self):
        _, items = sort_source(tf("""
            zeta {}
            output "o" {}
            alpha {}
            variable "v" {}
        """))
        self.assertEqual([i.address for i in items], ["variable.v", "output.o", "alpha", "zeta"])

    def test_custom_order(self):
        _, items = sort_source(
            tf("""
                variable "v" {}
                output "o" {}
            """),
            order=("output", "variable"),
        )
        self.assertEqual([i.type for i in items], ["output", "variable"])

    def test_same_address_keeps_original_order(self):
        source = """
            provider "aws" {
              region = "us-east-1"
            }
            provider "aws" {
              alias  = "west"
              region = "us-west-2"
            }
        """
        self.assertEqual(sort(source), sort(sort(source)))
        self.assertLess(sort(source).index("us-east-1"), sort(source).index("us-west-2"))

    def test_unquoted_labels(self):
        _, items = sort_source("resource b c {}\nresource a d {}\n")
        self.assertEqual([i.labels for i in items], [("a", "d"), ("b", "c")])


class CommentTests(unittest.TestCase):
    def test_comments_move_with_their_block(self):
        source = """
            # bucket for logs
            resource "x" "logs" {
              name = "logs" # inline
            }

            /*
             * main web server
             */
            resource "x" "app" {} // trailing
        """
        self.assertEqual(
            sort(source),
            tf("""
                /*
                 * main web server
                 */
                resource "x" "app" {} // trailing

                # bucket for logs
                resource "x" "logs" {
                  name = "logs" # inline
                }
            """),
        )

    def test_header_comment_stays_at_top(self):
        source = """
            # Copyright header

            variable "b" {}
            variable "a" {}
        """
        self.assertEqual(
            sort(source),
            tf("""
                # Copyright header

                variable "a" {}

                variable "b" {}
            """),
        )

    def test_detached_comment_moves_with_next_block(self):
        source = """
            variable "z" {}

            # section note

            variable "b" {}
            variable "a" {}
        """
        self.assertEqual(
            sort(source),
            tf("""
                variable "a" {}

                # section note

                variable "b" {}

                variable "z" {}
            """),
        )

    def test_trailing_comment_stays_at_end(self):
        source = """
            variable "b" {}
            variable "a" {}

            # end of file
        """
        self.assertTrue(sort(source).endswith('variable "b" {}\n\n# end of file\n'))

    def test_braces_in_comments_are_ignored(self):
        source = """
            variable "b" {
              # } not a close
              // { not an open
              /* } */
            }
            variable "a" {}
        """
        self.assertTrue(sort(source).startswith('variable "a" {}\n\nvariable "b" {'))


class SyntaxTests(unittest.TestCase):
    def test_braces_in_strings_and_interpolation(self):
        source = """
            locals {
              b = "}{ ${lookup({ a = "}" }, "a")} $${literal} %{ if true }x%{ endif }"
            }
            variable "a" {}
        """
        result = sort(source)
        self.assertTrue(result.startswith('variable "a" {}'))
        self.assertIn('lookup({ a = "}" }, "a")', result)

    def test_heredoc(self):
        source = """
            resource "x" "b" {
              policy = <<-EOT
                {
                  "unbalanced": "}"
                EOT
            }
            resource "x" "a" {
              script = <<EOF
            echo "{"
            EOF
            }
        """
        result = sort(source)
        self.assertTrue(result.startswith('resource "x" "a" {\n  script = <<EOF\necho "{"\nEOF\n}\n'))
        self.assertIn('"unbalanced": "}"', result)

    def test_nested_blocks_and_lists(self):
        source = """
            resource "x" "b" {
              tags = {
                a = [1, (2 + 3)]
              }
              dynamic "ingress" {
                for_each = []
                content {}
              }
            }
            resource "x" "a" {}
        """
        result = sort(source)
        self.assertTrue(result.startswith('resource "x" "a" {}\n\nresource "x" "b" {'))
        self.assertTrue(result.endswith("    content {}\n  }\n}\n"))

    def test_tfvars_attributes(self):
        source = """
            region   = "us-east-1"
            ami_list = [
              "a",
              "b",
            ]
            env = "dev"
        """
        self.assertEqual(
            sort(source),
            tf("""
                ami_list = [
                  "a",
                  "b",
                ]

                env = "dev"
                region   = "us-east-1"
            """),
        )

    def test_crlf_is_preserved(self):
        source = 'variable "b" {}\r\nvariable "a" {\r\n}\r\n'
        self.assertEqual(sort_source(source)[0], 'variable "a" {\r\n}\r\n\r\nvariable "b" {}\r\n')

    def test_missing_final_newline(self):
        self.assertEqual(sort_source('variable "b" {}\nvariable "a" {}')[0], 'variable "a" {}\n\nvariable "b" {}\n')

    def test_empty_and_comment_only_files_unchanged(self):
        for source in ("", "\n\n", "# just a comment\n"):
            self.assertEqual(sort_source(source)[0], source)

    def test_parse_errors(self):
        cases = {
            'variable "a" {\n': "unclosed",
            'variable "a" }\n': "unexpected '}'",
            'variable "a" {\n  x = "oops\n}\n': "unterminated string",
            "x = <<EOF\nnever closed\n": "unterminated heredoc",
            "/* never closed\n": "unterminated block comment",
            "= 1\n": "expected a block or attribute",
        }
        for source, message in cases.items():
            with self.subTest(source=source), self.assertRaisesRegex(ParseError, message):
                sort_source(source)

    def test_error_reports_line_and_column(self):
        with self.assertRaises(ParseError) as ctx:
            sort_source('variable "a" {}\nvariable "b" ]\n')
        self.assertEqual((ctx.exception.line, ctx.exception.col), (2, 14))


if __name__ == "__main__":
    unittest.main()
