from typing import Union
import math
from Interpretors.ExcelInterpretor import ExcelInterpretor
from Interpretors.WordInterpretor import WordInterpretor
from Config import Config
from Stategies.AvalStrat.StyleBinder import InterlacedStyleBinder, StyleBinder
from Types import Style, Type
from Stategies.AvalStrat.Measured import Measured
from Stategies.AvalStrat.Measurer import Measurer
from Stategies.AvalStrat.Question import Question


class AvaliationStrategy:
    def __init__(self, parser: Union[ExcelInterpretor, WordInterpretor], name_divider: str = "[") -> None:
        self.parser = parser
        self.name_divider = name_divider

    # depende bastante de excel para excel e do que queremos fazer com o excel
    def parse(self) -> list[Question]:
        self.result: list = []
        config_layout: Config = self.parser.get_config()
        file = self.parser.get_target_file()

        # Pega em todas as perguntas do layout
        questions = config_layout.get_type(Type.QUESTIONS)[0]["questions"]
        question_list: list[Question] = self.__get_questions(questions)

        # Pega em todos os avaliadores
        measurer_label = config_layout.get_type(Type.MEASURER)[0]
        measurer_list: list[Measurer] = self.__get_measurers(measurer_label)
        
        # Pega em todos os avaliados
        measured_names = config_layout.get_type(Type.MEASURED)[0]["names"]
        measured_list: list[Measured] = self.__get_measured(measured_names, question_list)

        # Avalia cada avaliado com cada avaliador
        # e guarda o resultado no próprio avaliado
        for measurer in measurer_list:
            for measured in measured_list:    
                measurer.evaluate(measured, file)

        return Question.mix_questions(question_list)

    # Parte mais complexa do código todo
    def convert_to_layout(self, question_list: list[Question]) -> Config:
        output = {"layout": []}
        final_layout = output["layout"]

        config = self.parser.get_config()

        question_names = self.__get_questions_names(question_list)
        num_questions = len(question_names)
        
        self.__header_conversion(config, final_layout, question_names, num_questions)
        self.__content_conversion(config, final_layout, question_list, num_questions)        
        
        result = Config(read_layout_from_file=False, layout=output)
        return result

    def __header_conversion(self, config: Config, final_layout: list, question_names: list[str], num_questions: int):

        bg_color_interlaced_binder = InterlacedStyleBinder(
            type=Style.BG_COLOR,
            style1="FFFFFF",
            style2="DDDDDD",
            initial_content=list(question_names[0])[0]
        )

        for leaf in config.leaf_iter("output"):
            dimentions = config.process_dimentions_of(Type(leaf["type"]), "output")
            break_line = True if leaf["type"] == Type.HEADER.name else False
            

            if leaf["type"] == Type.MEASURE.name:
                internal_index = 0

                bg_color_interlaced_binder.prep(item=leaf)

                for question_name in question_names:
                    bg_color_interlaced_binder.iter_bind(item=leaf, current_content=list(question_name)[0])
                    self.__add_item_to_layout(
                        end_result = final_layout, 
                        item = leaf, 
                        label=question_name,  
                        row_span= config.process_dimentions_of(Type.MEASURED, "output")["row-span"], 
                        col_span= dimentions["col-span"], 
                        break_line= internal_index == (num_questions - 1),
                    ) 
                    
                    internal_index += 1
                
                bg_color_interlaced_binder.unbind(leaf)

                continue

            if leaf["type"] == Type.HEADER.name:
                dimentions = config.process_dimentions_of(Type.HEADER, "output", self.__get_max_span(config, num_questions))
            
            self.__add_item_to_layout(
                end_result = final_layout, 
                item = leaf, 
                label= self.__get_label(leaf),  
                row_span= dimentions["row-span"], 
                col_span= dimentions["col-span"], 
                break_line= break_line,
            ) 
        
    def __content_conversion(self, config: Config, final_layout: list, question_list: list[Question], num_questions: int):

        dimentions = config.process_dimentions_of(Type.MEASURE, "output")

        # Isto configura o conteúdo
        measured_list: list[Measured] = self.__get_measured_list(question_list)
        measurer_list: list[Measurer] = measured_list[0].get_measurers()


        # Contém todas as informações configuradas nos arquivos json
        measure_leaf = config.get_type(Type.MEASURE, config.get_data("output"))[0]

        # passo intermediário, os dados estavam muito desorganizados e era dificil colocá-los no estado correto
        organized_content = self.__organize_content(measurer_list, question_list)

        bg_color_interlaced_binder = InterlacedStyleBinder(
            type=Style.BG_COLOR,
            style1="FFFFFF",
            style2="DDDDDD",
            initial_content=list(question_list[0].get_question_without_name(self.name_divider))[0]
        )
        
        # measurer -> measured -> grade
        for measurer in measurer_list:
            index = 0

            self.__add_item_to_layout(
                label= measurer.get_name(),
                end_result = final_layout,
                item = measure_leaf,
                row_span= dimentions["row-span"] * len(measured_list),
                col_span= config.process_dimentions_of(Type.MEASURER, "output")["col-span"],
                major= True,
                major_span= len(measured_list),
            )

            observations_already_added: list[Question] = []

            for measured in measured_list:
                self.__add_item_to_layout(
                    label= measured.get_name(),
                    col_span= config.process_dimentions_of(Type.MEASURED, "output")["col-span"],
                    row_span= dimentions["row-span"],
                    end_result = final_layout,
                    item = measure_leaf,
                    offset_col= (index != 0) * config.process_dimentions_of(Type.MEASURER, "output")["col-span"],
                )

                bg_color_interlaced_binder.prep(item=measure_leaf)

                internal_index = 0

                for grade in organized_content[measurer.get_name()][measured.get_name()]:
                    
                    question: Question = grade["question"]
                    note = grade["grade"]

                    question_number: str = question.get_question_letter(0)
                    is_observation = question.get_question_type() == Type.OBSERVATION
                    
                    if is_observation and (note in observations_already_added):
                        continue
                    elif is_observation:
                        observations_already_added.append(note)

                    bg_color_interlaced_binder.iter_bind(item=measure_leaf, current_content=question_number)

                    # styles
                    border_style_binder = StyleBinder(Style.BORDER, self.__get_item_property(measure_leaf, Style.BORDER, "thin"))
                    border_color_binder = StyleBinder(Style.BORDER_COLOR, self.__get_item_property(measure_leaf, Style.BORDER_COLOR, "000000"))
                    
                    self.__add_item_to_layout(
                        label= note,
                        col_span= dimentions["col-span"],
                        row_span= dimentions["row-span"] if not is_observation else config.process_dimentions_of(Type.MEASURER, "output")["col-span"],
                        end_result = final_layout,
                        break_line= internal_index == (num_questions - 1),
                        item = measure_leaf,
                        style_list=[border_style_binder, border_color_binder],
                        major = is_observation,
                        major_span= len(measured_list),
                    )

                    internal_index += 1

                bg_color_interlaced_binder.unbind(measure_leaf)
                
                

                index += 1

    # passo intermediario necessário para organizar os dados
    # extremamente ineficiente...
    def __organize_content(self, measurer_list: list[Measurer], question_list: list[Question]) -> dict[str: dict[str: list[int]]]:
        
        tmp_result = {}

        for measurer in measurer_list:
            for question in question_list:
                for grade, measured in question.get_grade_by_measurer(measurer):
                    if not tmp_result.get(measurer.get_name()):
                        tmp_result.update({
                            measurer.get_name(): {}
                        })
                    if not tmp_result[measurer.get_name()].get(measured.get_name()):
                        tmp_result[measurer.get_name()].update({
                            measured.get_name(): []
                        })
                    tmp_result[measurer.get_name()][measured.get_name()].append({"grade": grade, "question": question})
        
        return tmp_result
        
    def __get_measured_list(self, question_list: list[Question]) -> list[Measured]:
        measured_list: list[Measured] = []
        for question in question_list:
            for _, measured, _ in question.get_grades():
                if measured not in measured_list:
                    measured_list.append(measured)
        return measured_list
    
    def __get_questions_names(self, question_list: list[Question]) -> list[str]:
        questions_names: list[str] = []
        for question in question_list:
            question_label = question.get_question_without_name(self.name_divider)
            if question_label not in questions_names:
                questions_names.append(question_label)
        return questions_names

    def __get_label(self, element) -> str:
        try:
            return element["label"]
        except:
            return "Label não definido"
        
    def __get_max_span(self, config: Config, n_questions: int, property: str = "col-span") -> int:
        measured_col_span = config.process_dimentions_of(Type.MEASURED, "output")[property]
        measurer_col_span = config.process_dimentions_of(Type.MEASURER, "output")[property]
        question_col_span = config.process_dimentions_of(Type.MEASURE, "output")[property] * n_questions
        
        return measured_col_span + measurer_col_span + question_col_span
    
    def __add_item_to_layout(self, end_result: list, item: dict, label: str, row_span: int, col_span: int, break_line: bool = False, major: bool = False, major_span: int = 0, offset_col: int = 0, style_list: list[StyleBinder] = []):

        if len(style_list) > 0:
            for style in style_list:
                style.bind(item)
            
        end_result.append({
            Style.LABEL.value[0]: label,
            Style.COL_SPAN.value[0]: col_span,
            Style.ROW_SPAN.value[0]: row_span,
            Style.MAJOR.value[0]: major,
            Style.MAJOR_SPAN.value[0]: major_span,

            Style.BG_COLOR.value[0]: self.__get_item_property(item, Style.BG_COLOR, "ffffff"),
            Style.TEXT_COLOR.value[0]: self.__get_item_property(item, Style.TEXT_COLOR, "000000"),
            Style.X_ALIGNMENT.value[0]: self.__get_item_property(item, Style.X_ALIGNMENT, "center"),
            Style.Y_ALIGNMENT.value[0]: self.__get_item_property(item, Style.Y_ALIGNMENT, "center"),
            Style.BORDER.value[0]: self.__get_item_property(item, Style.BORDER, None),
            Style.BORDER_COLOR.value[0]: self.__get_item_property(item, Style.BORDER_COLOR, "000000"),

            "offset-col": offset_col,
            "break-line": break_line,
        })

        if len(style_list) > 0:
            for style in style_list:
                style.unbind(item)

    def __get_item_property(self, item, style: Style, default_to = None):
        try:
            return item[style.value[0]]
        except:
            return default_to
    
    def __get_questions(self, questions_in_layout) -> list[Question]:
        question_list: list = []
        for question in questions_in_layout:
            columns: list[tuple] = self.parser.find_index_and_value_of_column(question["label"])

            if type(columns[0]) == int:
                question_list.append(Question(columns[0], columns[1], question["type"]))
                continue

            for column in columns:
                question_list.append(Question(column[0], column[1], question["type"]))
        
        return question_list

    def __get_measurers(self, measurers_in_layout) -> list[Measurer]:
        measurer_index: int = self.parser.find_index_and_value_of_column(measurers_in_layout["label"])
        measurers = self.parser.get_column_values(measurer_index[0])

        measurers_list: list[Measurer] = []
        for measurer in measurers:
            measurers_list.append(Measurer(measurer[1], measurer[0]))

        return measurers_list

    def __get_measured(self, measured_names_in_layout, question_list: list[Question]) -> list[Measured]:
        measured_list: list[Measured] = []
        for measured_name in measured_names_in_layout:
            measured_list.append(Measured(measured_name, question_list))
        return measured_list
    
    # Pode ser util
    def __debug(self, measured_list: list[Measured]) -> str:
        final_str = ""
        for measured in measured_list:
            for question in measured.get_questions():
                for grade, measurer in question.get_grades():
                    final_str += f"\n\nAvaliado [{measured.get_name()}]\nAvaliador [{measurer.get_name()}]\n{question.get_question()}\nNota {grade}"
        return final_str
